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
#
# The list comes from pyproject.toml rather than being repeated here. Repeating
# it is the trap: you add a package, it works with `uv run`, and the deployed
# job dies with ModuleNotFoundError because the image never got it.
RUN pip install --no-cache-dir uv
COPY pyproject.toml ./
RUN uv pip install --system --no-cache -r pyproject.toml

COPY src/ ./src/

CMD ["python", "-m", "src.pipeline"]
