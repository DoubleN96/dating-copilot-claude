FROM python:3.12-slim
RUN pip install --no-cache-dir cryptography==46.0.3 tzdata
WORKDIR /app
COPY app.py ia.py ui.py ./
COPY static ./static
ENV DB_PATH=/data/celestia.db PORT=8990 PYTHONUNBUFFERED=1
EXPOSE 8990
HEALTHCHECK CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8990/robots.txt')"
CMD ["python", "app.py"]
