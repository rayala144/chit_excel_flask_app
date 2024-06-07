FROM python:3.11.6

# Set the working directory in the container
WORKDIR /WebAppExcel

# Copy the requirements file into the container at /WebAppExcel
COPY requirements.txt /WebAppExcel/

# Install any needed packages specified in requirements.txt
RUN pip install -r requirements.txt

# Copy the current directory contents into the container at /WebAppExcel
COPY . /WebAppExcel/

# Define environment variable
ENV FLASK_APP=app.py

# Expose port 8080 for the Flask application
EXPOSE 8080


CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]
