import os
import sys
from io import BytesIO

import convertapi
from convertapi import UploadIO
from openpyxl import load_workbook

from mod_excel import prepare_workbook_for_pdf


def _get_api_credentials():
    return os.environ.get("CONVERTAPI_SECRET") or os.environ.get("CONVERT_API_TOKEN")


def convert_excel_to_pdf(xlsx_bytes: bytes, filename: str) -> bytes:
    credentials = _get_api_credentials()
    if not credentials:
        raise ValueError(
            "PDF export is not configured. Set the CONVERTAPI_SECRET environment variable."
        )

    convertapi.api_credentials = credentials
    upload = UploadIO(xlsx_bytes, filename)
    result = convertapi.convert("pdf", {"File": upload}, from_format="xlsx")
    return result.file.io.read()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python convert_to_pdf.py <input.xlsx> [output.pdf]")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = (
        sys.argv[2]
        if len(sys.argv) > 2
        else os.path.splitext(input_path)[0] + ".pdf"
    )

    with open(input_path, "rb") as f:
        workbook = load_workbook(filename=BytesIO(f.read()))
        xlsx_bytes = prepare_workbook_for_pdf(workbook)
        pdf_bytes = convert_excel_to_pdf(xlsx_bytes, os.path.basename(input_path))

    with open(output_path, "wb") as f:
        f.write(pdf_bytes)

    print(f"Saved {output_path}")
