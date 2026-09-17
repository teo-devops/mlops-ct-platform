# The Listing Engine steps image: ctsteps + the plugin. This is what the
# pipeline (and the drift monitor) run.
ARG BASE=ctsteps-base:0.1.0
FROM ${BASE}
USER root
WORKDIR /opt/use-case
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .
USER 10001
ENV CT_USE_CASE=listing_engine:use_case
