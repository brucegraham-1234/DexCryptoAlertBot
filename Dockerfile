FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py ./

ENV PORT=8080
ENV DB_PATH=/app/alerts.db

CMD ["python", "main.py"]
