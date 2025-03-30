# Use official Python image as base
FROM python:3.11

# Set working directory
WORKDIR /app

# Copy dependencies file and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire backend app
COPY . .

# Expose port
EXPOSE 8000

# Run FastAPI server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
