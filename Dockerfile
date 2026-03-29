FROM ghcr.io/meta-pytorch/openenv-base:latest

WORKDIR /app

# Copy pyproject.toml + requirements first for layer caching
COPY pyproject.toml .
COPY server/requirements.txt ./server/requirements.txt

# Install server runtime deps + openenv-core
RUN pip install --no-cache-dir -r server/requirements.txt

# Copy all source files
COPY __init__.py .
COPY models.py .
COPY client.py .
COPY inference.py .
COPY openenv.yaml .
COPY server/ server/

# Install this project as a package so imports resolve correctly
RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000"]
