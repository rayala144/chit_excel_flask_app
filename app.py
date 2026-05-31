import logging
import os
import time
from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from flask import Flask, abort, redirect, render_template, request, send_file, url_for
from openpyxl import load_workbook
from postgrest.exceptions import APIError
from supabase import Client, create_client
from convert_to_pdf import convert_excel_to_pdf
from mod_excel import add_suffix_to_filename, prepare_workbook_for_pdf, update_excel

load_dotenv()

logger = logging.getLogger(__name__)

app = Flask(__name__)

BUCKET_NAME = "chit-files"
IST = ZoneInfo("Asia/Kolkata")
_supabase_client: Client | None = None
_supabase_init_attempted = False


def format_timestamp_ist(value) -> str | None:
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S")


def _supabase_credentials() -> tuple[str, str] | None:
    url = (os.environ.get("SUPABASE_URL") or "").strip()
    key = (
        os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_KEY")
        or os.environ.get("SUPABASE_ANON_KEY")
        or ""
    ).strip()
    if not url or not key:
        return None
    return url, key


def get_supabase() -> Client | None:
    """Return Supabase client, or None if unset/invalid (app still runs)."""
    global _supabase_client, _supabase_init_attempted

    if _supabase_client is not None:
        return _supabase_client

    if _supabase_init_attempted:
        return None

    _supabase_init_attempted = True
    credentials = _supabase_credentials()
    if not credentials:
        return None

    url, key = credentials
    try:
        _supabase_client = create_client(url, key)
    except Exception as exc:
        logger.warning("Supabase disabled: %s", exc)
        _supabase_client = None

    return _supabase_client


def _pdf_download_name(excel_filename: str) -> str:
    base, _ = os.path.splitext(excel_filename)
    return f"{base}_updated.pdf"


def upload_to_supabase_storage(file_bytes: bytes, destination_path: str) -> str:
    """Uploads bytes to Supabase storage bucket and returns the public download URL."""
    supabase = get_supabase()
    if not supabase:
        return ""

    supabase.storage.from_(BUCKET_NAME).upload(
        path=destination_path,
        file=file_bytes,
        file_options={"content-type": "application/octet-stream", "upsert": "true"},
    )
    return supabase.storage.from_(BUCKET_NAME).get_public_url(destination_path)


def _storage_path_from_url(url: str) -> str | None:
    if not url:
        return None
    marker = f"/{BUCKET_NAME}/"
    if marker in url:
        return url.split(marker, 1)[1].split("?")[0]
    return None


def _processed_storage_path(record: dict) -> str | None:
    path = record.get("processed_storage_path")
    if path:
        return path
    return _storage_path_from_url(record.get("processed_file_url") or "")


def _processed_download_name(record: dict) -> str:
    if record.get("processed_filename"):
        return record["processed_filename"]
    path = _processed_storage_path(record)
    if path:
        return os.path.basename(path)
    original = record.get("original_filename") or "file"
    if record.get("output_format") == "pdf":
        return _pdf_download_name(original)
    return add_suffix_to_filename(original, "_updated")


def _is_schema_column_error(exc: APIError) -> bool:
    code = getattr(exc, "code", None)
    if str(code) in ("42703", "PGRST204"):
        return True
    message = getattr(exc, "message", "") or str(exc)
    return (
        ("does not exist" in message and "column" in message)
        or "Could not find" in message
    )


_HISTORY_QUERY_PLANS = (
    {
        "select": (
            "id, original_filename, output_format, processed_file_url, "
            "processed_storage_path, processed_filename, created_at"
        ),
        "order": "created_at",
    },
    {
        "select": "id, original_filename, output_format, processed_file_url, created_at",
        "order": "created_at",
    },
    {
        "select": "id, original_filename, output_format, processed_file_url",
        "order": "id",
    },
)

_DOWNLOAD_QUERY_PLANS = (
    (
        "id, original_filename, output_format, processed_file_url, "
        "processed_storage_path, processed_filename, uploaded_file_url"
    ),
    "id, original_filename, output_format, processed_file_url, uploaded_file_url",
)


def _fetch_record(record_id: str) -> dict | None:
    supabase = get_supabase()
    if not supabase or not record_id:
        return None

    last_error = None
    for columns in _DOWNLOAD_QUERY_PLANS:
        try:
            result = (
                supabase.table("file_logs")
                .select(columns)
                .eq("id", record_id)
                .limit(1)
                .execute()
            )
            if result.data:
                return result.data[0]
        except APIError as exc:
            if _is_schema_column_error(exc):
                last_error = exc
                continue
            raise

    if last_error:
        logger.warning("Could not load file record: %s", last_error)
    return None


def _delete_storage_paths(paths: list[str]) -> None:
    supabase = get_supabase()
    if not supabase or not paths:
        return

    unique_paths = list(dict.fromkeys(p for p in paths if p))
    if not unique_paths:
        return

    try:
        supabase.storage.from_(BUCKET_NAME).remove(unique_paths)
    except Exception as exc:
        logger.warning("Failed to delete storage files: %s", exc)


def delete_file_record(record_id: str) -> bool:
    record = _fetch_record(record_id)
    if not record:
        return False

    supabase = get_supabase()
    if not supabase:
        return False

    storage_paths = []
    processed_path = _processed_storage_path(record)
    if processed_path:
        storage_paths.append(processed_path)
    original_path = _storage_path_from_url(record.get("uploaded_file_url") or "")
    if original_path:
        storage_paths.append(original_path)
    _delete_storage_paths(storage_paths)

    supabase.table("file_logs").delete().eq("id", record_id).execute()
    return True

def fetch_file_history(limit: int = 50) -> list[dict]:
    supabase = get_supabase()
    if not supabase:
        return []

    last_error = None
    for plan in _HISTORY_QUERY_PLANS:
        try:
            result = (
                supabase.table("file_logs")
                .select(plan["select"])
                .order(plan["order"], desc=True)
                .limit(limit)
                .execute()
            )
            return result.data or []
        except APIError as exc:
            if _is_schema_column_error(exc):
                last_error = exc
                continue
            raise

    logger.warning("Could not fetch file history: %s", last_error)
    return []


def download_processed_file(record_id: str) -> tuple[bytes, str, str]:
    supabase = get_supabase()
    if not supabase:
        abort(503, "Storage is not configured.")

    record = _fetch_record(record_id)
    if not record:
        abort(404)

    storage_path = _processed_storage_path(record)
    if not storage_path:
        abort(404)

    file_bytes = supabase.storage.from_(BUCKET_NAME).download(storage_path)
    download_name = _processed_download_name(record)
    mimetype = (
        "application/pdf"
        if record.get("output_format") == "pdf"
        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    return file_bytes, download_name, mimetype


def log_to_database(
    orig_name,
    format_type,
    orig_url,
    proc_url,
    proc_path,
    proc_filename,
):
    """Inserts metadata logs into the PostgreSQL database."""
    supabase = get_supabase()
    if not supabase:
        return

    minimal_data = {
        "original_filename": orig_name,
        "output_format": format_type,
        "uploaded_file_url": orig_url,
        "processed_file_url": proc_url,
    }
    extended_data = {
        **minimal_data,
        "processed_storage_path": proc_path,
        "processed_filename": proc_filename,
    }

    for payload in (extended_data, minimal_data):
        try:
            supabase.table("file_logs").insert(payload).execute()
            return
        except APIError as exc:
            if _is_schema_column_error(exc):
                continue
            raise

    logger.warning("Could not insert file log for %s", orig_name)
@app.route("/", methods=["GET", "POST"])
def upload_file():
    if request.method == "POST":
        file = request.files["file"]
        output_format = request.form.get("output_format", "excel")

        if file.filename:
            if file.filename.endswith(".xlsx") or file.filename.endswith(".xls"):
                original_file_bytes = file.read()

                my_workbook = load_workbook(filename=BytesIO(original_file_bytes))
                updated_workbook = update_excel(my_workbook)

                output_excel_buffer = BytesIO()
                updated_workbook.save(output_excel_buffer)
                processed_bytes = output_excel_buffer.getvalue()

                output_file = add_suffix_to_filename(file.filename, "_updated")

                timestamp_prefix = str(int(time.time()))
                orig_cloud_path = f"{timestamp_prefix}/original_{file.filename}"
                proc_cloud_path = f"{timestamp_prefix}/{output_file}"
                proc_download_name = os.path.basename(proc_cloud_path)

                if output_format == "pdf":
                    try:
                        pdf_xlsx_bytes = prepare_workbook_for_pdf(updated_workbook)
                        processed_bytes = convert_excel_to_pdf(pdf_xlsx_bytes, output_file)
                        proc_download_name = _pdf_download_name(file.filename)
                        proc_cloud_path = f"{timestamp_prefix}/{proc_download_name}"
                    except ValueError as exc:
                        return render_template("index.html", error=str(exc))
                    except Exception:
                        return render_template(
                            "index.html",
                            error="PDF conversion failed. Please try again or download as Excel.",
                        )

                if get_supabase():
                    try:
                        uploaded_url = upload_to_supabase_storage(
                            original_file_bytes, orig_cloud_path
                        )
                        processed_url = upload_to_supabase_storage(
                            processed_bytes, proc_cloud_path
                        )
                        log_to_database(
                            file.filename,
                            output_format,
                            uploaded_url,
                            processed_url,
                            proc_cloud_path,
                            proc_download_name,
                        )
                    except Exception as db_err:
                        logger.exception("Cloud logging failed: %s", db_err)

                mimetype = (
                    "application/pdf"
                    if output_format == "pdf"
                    else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                download_name = (
                    _pdf_download_name(file.filename)
                    if output_format == "pdf"
                    else output_file
                )

                return send_file(
                    BytesIO(processed_bytes),
                    as_attachment=True,
                    mimetype=mimetype,
                    download_name=download_name,
                )

            return render_template(
                "index.html", error="Only Excel files (.xlsx, .xls) are allowed."
            )

        return render_template("index.html", error="Please choose a file to upload.")

    return render_template("index.html")


@app.route("/history")
def file_history():
    records = fetch_file_history()
    for record in records:
        record["created_at"] = format_timestamp_ist(record.get("created_at"))
    deleted = request.args.get("deleted") == "1"
    return render_template(
        "history.html",
        records=records,
        storage_enabled=bool(get_supabase()),
        deleted=deleted,
    )


@app.route("/history/<record_id>/delete", methods=["POST"])
def delete_stored_file(record_id):
    if not delete_file_record(record_id):
        abort(404)
    return redirect(url_for("file_history", deleted=1))

@app.route("/download/<record_id>")
def download_stored_file(record_id):
    file_bytes, download_name, mimetype = download_processed_file(record_id)
    return send_file(
        BytesIO(file_bytes),
        as_attachment=True,
        mimetype=mimetype,
        download_name=download_name,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)