import logging
import os
import time
from io import BytesIO

from dotenv import load_dotenv
from flask import Flask, render_template, request, send_file
from openpyxl import load_workbook
from supabase import Client, create_client

from convert_to_pdf import convert_excel_to_pdf
from mod_excel import add_suffix_to_filename, prepare_workbook_for_pdf, update_excel

load_dotenv()

logger = logging.getLogger(__name__)

app = Flask(__name__)

_supabase_client: Client | None = None
_supabase_init_attempted = False


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

    bucket_name = "chit-files"
    supabase.storage.from_(bucket_name).upload(
        path=destination_path,
        file=file_bytes,
        file_options={"content-type": "application/octet-stream"},
    )
    return supabase.storage.from_(bucket_name).get_public_url(destination_path)


def log_to_database(orig_name, format_type, orig_url, proc_url):
    """Inserts metadata logs into the PostgreSQL database."""
    supabase = get_supabase()
    if not supabase:
        return

    data = {
        "original_filename": orig_name,
        "output_format": format_type,
        "uploaded_file_url": orig_url,
        "processed_file_url": proc_url,
    }
    supabase.table("file_logs").insert(data).execute()


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

                if output_format == "pdf":
                    try:
                        pdf_xlsx_bytes = prepare_workbook_for_pdf(updated_workbook)
                        processed_bytes = convert_excel_to_pdf(pdf_xlsx_bytes, output_file)
                        proc_cloud_path = f"{timestamp_prefix}/{_pdf_download_name(file.filename)}"
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
                            file.filename, output_format, uploaded_url, processed_url
                        )
                    except Exception as db_err:
                        logger.warning("Cloud logging failed: %s", db_err)

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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
