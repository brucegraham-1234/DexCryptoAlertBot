# Use a small Python base image
FROM python:3.10-slim

# Create app directory
WORKDIR /app

# Install deps first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY main.py .

# Cloud Run provides $PORT; Flask will bind to it
ENV PORT=8080

# Run the bot+Flask app
CMD ["python", "main.py"]
