# ctserve-base: the serving-side contract runtime. Use-case API images build
# FROM it and add their application.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /opt/ctserve
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .
