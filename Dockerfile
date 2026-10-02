FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080 APP_ENV=production
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home appuser
COPY app.py gunicorn.conf.py ./
COPY schedule ./schedule
COPY data/sample.csv ./data/sample.csv
USER 10001
EXPOSE 8080
CMD ["gunicorn", "--config", "gunicorn.conf.py", "app:app"]
