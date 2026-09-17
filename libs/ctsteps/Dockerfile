# ctsteps-base: the step contract runtime. Use-case images build FROM it and
# add their plugin. python:3.11 to mirror kserve/sklearnserver (pickles cross
# minor versions fine, but why take the risk).
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MLFLOW_DISABLE_AGENT_HINT=1 \
    GIT_CONFIG_GLOBAL=/tmp/gitconfig HOME=/tmp
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/ctsteps
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .
RUN useradd -u 10001 -r -s /usr/sbin/nologin steps
USER 10001
ENTRYPOINT []
CMD ["ctsteps", "--help"]
