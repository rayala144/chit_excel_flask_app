from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from postgrest.exceptions import APIError

import app
from mod_excel import add_suffix_to_filename


def test_add_suffix_to_filename():
    assert add_suffix_to_filename("report.xlsx", "_updated") == "report_updated.xlsx"
    assert (
        add_suffix_to_filename("folder/data.xls", "_updated").replace("\\", "/")
        == "folder/data_updated.xls"
    )


def test_format_timestamp_ist_from_utc_string():
    assert app.format_timestamp_ist("2026-05-21T10:30:00+00:00") == "2026-05-21 16:00:00"
    assert app.format_timestamp_ist("2026-05-21T10:30:00Z") == "2026-05-21 16:00:00"


def test_format_timestamp_ist_from_naive_string():
    assert app.format_timestamp_ist("2026-05-21T10:30:00") == "2026-05-21 16:00:00"


def test_format_timestamp_ist_from_datetime():
    dt = datetime(2026, 5, 21, 10, 30, tzinfo=ZoneInfo("UTC"))
    assert app.format_timestamp_ist(dt) == "2026-05-21 16:00:00"


def test_format_timestamp_ist_none():
    assert app.format_timestamp_ist(None) is None
    assert app.format_timestamp_ist("") is None


def test_storage_path_from_url():
    url = "https://example.supabase.co/storage/v1/object/public/chit-files/123/file.xlsx"
    assert app._storage_path_from_url(url) == "123/file.xlsx"
    assert app._storage_path_from_url("") is None


def test_processed_download_name_prefers_stored_filename():
    record = {
        "processed_filename": "custom_updated.xlsx",
        "original_filename": "input.xlsx",
        "output_format": "excel",
    }
    assert app._processed_download_name(record) == "custom_updated.xlsx"


def test_processed_download_name_pdf_fallback():
    record = {"original_filename": "input.xlsx", "output_format": "pdf"}
    assert app._processed_download_name(record) == "input_updated.pdf"


def test_is_schema_column_error_postgrest_code():
    exc = APIError({"message": "missing column", "code": "PGRST204"})
    assert app._is_schema_column_error(exc) is True


def test_is_schema_column_error_postgres_code():
    exc = APIError({"message": 'column "foo" does not exist', "code": "42703"})
    assert app._is_schema_column_error(exc) is True


def test_is_schema_column_error_unrelated():
    exc = APIError({"message": "permission denied", "code": "42501"})
    assert app._is_schema_column_error(exc) is False
