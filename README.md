# Chit Excel Flask App

This application provides utilities for processing and updating Excel files related to chit fund data using Python and Flask. It leverages the `openpyxl` library to automate calculations and formatting in Excel workbooks.

## Features

- Automatically fills and sums values in Excel sheets.
- Adds calculated totals and grand totals.
- Supports updating Excel files with a custom suffix.
- Designed for integration with a Flask web application.

## Requirements

- Python 3.7+
- [openpyxl](https://openpyxl.readthedocs.io/en/stable/)
- Flask (if using with a web interface)

## Installation

1. Clone this repository:
    ```bash
    git clone <repo-url>
    cd chit_excel_flask_app
    ```

2. Install dependencies:
    ```bash
    pip install openpyxl flask
    ```

## Usage

You can use the core Excel processing functions in `mod_excel.py` as a standalone script or import them into your Flask app.

### Example

```python
from mod_excel import update_excel
import openpyxl

wb = openpyxl.load_workbook('your_file.xlsx')
updated_wb = update_excel(wb)
updated_wb.save('your_file_updated.xlsx')
```

## File Structure

- `mod_excel.py` - Core Excel processing logic.
- `README.md` - Project documentation.
