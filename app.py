import os

from flask import Flask, render_template, request, send_file
from io import BytesIO
from openpyxl import load_workbook

from convert_to_pdf import convert_excel_to_pdf
from mod_excel import add_suffix_to_filename, update_excel


app = Flask(__name__)


def _pdf_download_name(excel_filename: str) -> str:
    base, _ = os.path.splitext(excel_filename)
    return f"{base}_updated.pdf"


@app.route("/", methods=["GET", "POST"])
def upload_file():
    if request.method == "POST":
        file = request.files["file"]
        output_format = request.form.get("output_format", "excel")

        if file.filename:
            if file.filename.endswith(".xlsx") or file.filename.endswith(".xls"):
                my_workbook = load_workbook(filename=BytesIO(file.read()))
                updated_workbook = update_excel(my_workbook)

                output = BytesIO()
                updated_workbook.save(output)
                output.seek(0)

                output_file = add_suffix_to_filename(file.filename, "_updated")

                if output_format == "pdf":
                    try:
                        pdf_bytes = convert_excel_to_pdf(
                            output.getvalue(), output_file
                        )
                        return send_file(
                            BytesIO(pdf_bytes),
                            as_attachment=True,
                            mimetype="application/pdf",
                            download_name=_pdf_download_name(file.filename),
                        )
                    except ValueError as exc:
                        return render_template("index.html", error=str(exc))
                    except Exception:
                        return render_template(
                            "index.html",
                            error="PDF conversion failed. Please try again or download as Excel.",
                        )

                output.seek(0)
                return send_file(
                    output,
                    as_attachment=True,
                    mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    download_name=output_file,
                )

            return render_template(
                "index.html", error="Only Excel files (.xlsx, .xls) are allowed."
            )

        return render_template("index.html", error="Please choose a file to upload.")

    return render_template("index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
