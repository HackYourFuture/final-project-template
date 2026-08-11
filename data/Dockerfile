# Container image for the ingestion pipeline.
#
# Build:  docker build -t final-project-data .
# Run:    docker run --rm --env-file .env final-project-data
#
# This is the image you push to Azure Container Registry and run as a
# Container Apps Job, exactly as in Week 6.
FROM python:3.11-slim

WORKDIR /app

# Dependencies are copied first so Docker can cache the install layer. Change
# your source code and the rebuild stays fast; change dependencies and it does not.
COPY pyproject.toml ./
RUN pip install --no-cache-dir \
        "requests>=2.32.0" \
        "pydantic>=2.9.0" \
        "python-dotenv>=1.0.0" \
        "azure-identity>=1.19.0" \
        "azure-storage-blob>=12.23.0"

COPY src/ ./src/

CMD ["python", "-m", "src.pipeline"]
