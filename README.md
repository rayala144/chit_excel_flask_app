# Chit Excel Flask App

A Flask web application for processing chit-fund Excel workbooks. Upload an `.xlsx` or `.xls` file, run automated calculations and formatting, then download the updated Excel file or a PDF export. Optional Supabase integration stores uploads and processed files with a searchable history page.

## Features

### Excel processing
- Automatically fills and sums values across `Sheet2` and `Sheet3` based on reference data in `Sheet1`.
- Adds column totals and a bold **GRAND TOTAL** on `Sheet3`.
- Saves processed files with an `_updated` suffix (e.g. `report.xlsx` → `report_updated.xlsx`).

### Web interface
- Drag-and-drop upload on the home page.
- Download as **Excel** or **PDF**.
- Light / dark theme toggle (defaults to dark; preference saved in `localStorage`).
- Mobile-friendly layout, including a card-style history page on small screens.

### File history (Supabase)
- Stores original and processed files in a Supabase Storage bucket (`chit-files`).
- Logs metadata in a `file_logs` PostgreSQL table.
- **History page** (`/history`) lists past uploads with format badges and timestamps in **IST** (Indian Standard Time).
- Re-download processed files from history.
- Delete records (removes DB row and storage files).

### PDF export
- PDF conversion uses [ConvertAPI](https://www.convertapi.com/) (requires an API secret).
- Only `Sheet2` and `Sheet3` are included in the PDF output.

### Resilience
- App runs without Supabase or ConvertAPI configured; missing services disable only the related features.
- Database inserts fall back gracefully when optional `file_logs` columns are missing (older schemas).

## Requirements

- Python 3.11+ (recommended; 3.9+ may work)
- See `requirements.txt` for runtime dependencies
- See `requirements-dev.txt` for test dependencies

## Installation

1. Clone the repository:
   ```bash
   git clone <repo-url>
   cd chit_excel_flask_app
   ```

2. Create a virtual environment (optional but recommended):
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Linux/macOS
   .venv\Scripts\activate      # Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the project root (see [Environment variables](#environment-variables) below).

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SUPABASE_URL` | For history/storage | Your Supabase project URL |
| `SUPABASE_KEY` or `SUPABASE_SERVICE_KEY` | For history/storage | Supabase service role key (`eyJ...` JWT). Prefer service role for storage uploads and deletes. |
| `CONVERTAPI_SECRET` | For PDF export | ConvertAPI secret token |

If Supabase variables are unset, uploads still work but files are not stored and `/history` shows a configuration notice. If `CONVERTAPI_SECRET` is unset, PDF download returns an error message.

## Supabase setup

1. Create a Storage bucket named **`chit-files`** (public read if you use public URLs).
2. Run `schema.sql` in the Supabase SQL Editor to create or migrate the `file_logs` table:
   ```bash
   # File: schema.sql
   ```
3. Set `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` (or `SUPABASE_KEY`) in `.env` and in your deployment platform (e.g. Vercel).

## Running locally

```bash
python app.py
```

The app listens on `http://0.0.0.0:8080`.

With Gunicorn:

```bash
gunicorn -b 0.0.0.0:8080 app:app
```

## Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET, POST | Upload form and file processing |
| `/history` | GET | List stored file records |
| `/download/<record_id>` | GET | Download a processed file from history |
| `/history/<record_id>/delete` | POST | Delete a record and its storage files |

## Testing

Install dev dependencies and run the test suite:

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest tests/ -v
```

With coverage:

```bash
python -m pytest tests/ -v --cov=app --cov=mod_excel --cov-report=term-missing
```

Tests cover Excel logic, Flask routes, helper utilities, and Supabase schema fallbacks (mocked; no live credentials needed).

## CI/CD

- **`.github/workflows/ci.yml`** — runs pytest on push and pull requests to `master` and `new_features`.
- **`.github/workflows/docker-build-push.yml`** — builds Docker images; pushes to Docker Hub only on direct pushes to `master`.

## Deployment

- **Vercel** — configured via `vercel.json` (Python serverless build targeting `app.py`). Set environment variables in the Vercel dashboard.
- **Docker** — use the included `Dockerfile` for containerized deployment.

## Programmatic usage

You can also use the Excel helpers outside the web app:

```python
from io import BytesIO
from openpyxl import load_workbook
from mod_excel import update_excel

with open("your_file.xlsx", "rb") as f:
    workbook = load_workbook(filename=BytesIO(f.read()))

updated_workbook = update_excel(workbook)
updated_workbook.save("your_file_updated.xlsx")
```

## File structure

| Path | Purpose |
|------|---------|
| `app.py` | Flask routes, Supabase storage, and history |
| `mod_excel.py` | Core Excel processing logic |
| `convert_to_pdf.py` | ConvertAPI PDF export |
| `templates/index.html` | Upload UI |
| `templates/history.html` | File history UI |
| `schema.sql` | Supabase `file_logs` table migration |
| `tests/` | Pytest suite |
| `requirements.txt` | Production dependencies |
| `requirements-dev.txt` | Test dependencies |
| `vercel.json` | Vercel deployment config |
| `Dockerfile` | Container image definition |
