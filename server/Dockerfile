FROM ghcr.io/meta-pytorch/openenv-base:latest

WORKDIR /app

# Copy requirements first (layer caching)
COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all source
COPY models.py .
COPY client.py .
COPY inference.py .
COPY server/ server/
COPY openenv.yaml .

EXPOSE 8000

CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000"]
