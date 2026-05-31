from io import BytesIO
from unittest.mock import MagicMock

import pytest
from postgrest.exceptions import APIError

import app


def test_index_get(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"upload" in response.data.lower() or b"excel" in response.data.lower()


def test_history_without_storage(client):
    response = client.get("/history")
    assert response.status_code == 200
    assert b"Storage is not configured" in response.data


def test_upload_without_file_shows_error(client):
    response = client.post(
        "/",
        data={"file": (BytesIO(b""), ""), "output_format": "excel"},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    assert b"Please choose a file" in response.data


def test_upload_rejects_non_excel(client):
    response = client.post(
        "/",
        data={
            "file": (BytesIO(b"not excel"), "notes.txt"),
            "output_format": "excel",
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    assert b"Only Excel files" in response.data


def test_upload_excel_returns_processed_workbook(client, sample_xlsx_bytes):
    response = client.post(
        "/",
        data={
            "file": (BytesIO(sample_xlsx_bytes), "sample.xlsx"),
            "output_format": "excel",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert (
        response.mimetype
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "sample_updated.xlsx" in response.headers.get("Content-Disposition", "")
    assert len(response.data) > 0


def test_history_lists_records(monkeypatch, client):
    records = [
        {
            "id": "rec-1",
            "original_filename": "sample.xlsx",
            "output_format": "excel",
            "processed_file_url": "https://example.com/chit-files/1/out.xlsx",
            "created_at": "2026-05-21T10:30:00+00:00",
        }
    ]

    monkeypatch.setattr(app, "fetch_file_history", lambda limit=50: records)
    monkeypatch.setattr(app, "get_supabase", lambda: object())

    response = client.get("/history")
    assert response.status_code == 200
    assert b"sample.xlsx" in response.data
    assert b"2026-05-21 16:00:00 IST" in response.data


def test_log_to_database_falls_back_to_minimal_payload(monkeypatch):
    payloads = []

    class FakeQuery:
        def insert(self, payload):
            payloads.append(payload)
            if len(payloads) == 1:
                raise APIError(
                    {
                        "message": "Could not find the 'processed_filename' column",
                        "code": "PGRST204",
                    }
                )
            return self

        def execute(self):
            return MagicMock()

    fake_supabase = MagicMock()
    fake_supabase.table.return_value = FakeQuery()
    monkeypatch.setattr(app, "get_supabase", lambda: fake_supabase)

    app.log_to_database(
        "sample.xlsx",
        "excel",
        "https://example.com/original",
        "https://example.com/processed",
        "123/sample_updated.xlsx",
        "sample_updated.xlsx",
    )

    assert len(payloads) == 2
    assert payloads[0]["processed_filename"] == "sample_updated.xlsx"
    assert "processed_filename" not in payloads[1]
    assert payloads[1]["original_filename"] == "sample.xlsx"


def test_download_missing_record_returns_404(client, monkeypatch):
    monkeypatch.setattr(app, "get_supabase", lambda: object())
    monkeypatch.setattr(app, "_fetch_record", lambda record_id: None)

    response = client.get("/download/missing-id")
    assert response.status_code == 404
