# Use official Python image as base
FROM python:3.11

ENV TZ=America/Los_Angeles
RUN apt-get update && apt-get install -y tzdata

# Set working directory
WORKDIR /app

# Copy dependencies file and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# safer and clearer
ARG VITE_GOOGLE_MAPS_API_KEY
ENV VITE_GOOGLE_MAPS_API_KEY=$VITE_GOOGLE_MAPS_API_KEY

# Copy entire backend app
COPY . .
COPY gtfs_data /app/app/gtfs_data


# Expose port
EXPOSE 8000

# Run FastAPI server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
