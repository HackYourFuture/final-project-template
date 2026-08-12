# Container image for the ingestion pipeline.
#
# Build:  docker build -t final-project-data .
#
# Running it on your own machine will not authenticate: there is no `az login`
# and no Azure metadata service inside a container, so DefaultAzureCredential
# has nothing to use. The image gets its identity from Azure when the Container
# Apps job runs it. Locally, run `uv run python -m src.pipeline` instead.
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
