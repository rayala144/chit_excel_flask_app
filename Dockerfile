FROM python:3.11.4

COPY . /WebAppExcel/

WORKDIR /WebAppExcel

RUN pip install --upgrade pip && \
    pip install openpyxl==3.2.0b1 && \
    pip install Flask==3.0.0 && \
    pip install regex==2022.10.31

ENTRYPOINT ["python", "app.py", "--host", "127.0.0.1", "--port", "5000"]