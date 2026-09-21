ARG BASE=ctserve-base:0.1.0
FROM ${BASE}
ARG GIT_COMMIT=unknown
ENV ALE_GIT_COMMIT=${GIT_COMMIT}
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN useradd -u 10001 -r -s /usr/sbin/nologin api && chown -R api /srv
USER 10001
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
