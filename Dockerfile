FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for geospatial libraries
RUN apt-get update && apt-get install -y \
    libgeos-dev \
    libproj-dev \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy Python requirements
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

# Copy application code
COPY bluebreaks/ ./bluebreaks/

# Expose API port
EXPOSE 8000

# Run the FastAPI server
CMD ["uvicorn", "bluebreaks.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
