FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY wc2026_bot.py .

CMD ["python", "wc2026_bot.py"]
