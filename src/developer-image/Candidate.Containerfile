FROM node:24-bookworm-slim@sha256:d6aa754f16b3197301076f047b5def2f02ea1dbbc2ca920407d46d7ec7f87b20 AS frontend
WORKDIR /web
COPY src/research-portal/frontend/package.json src/research-portal/frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY src/research-portal/frontend/ ./
RUN npm run build

FROM python:3.13-slim-bookworm@sha256:a1165e272e578941b84abc79e4ab38a0305cd12803a5c4247979ac7655f4d641 AS runtime
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app \
    CALDOVA_PREVIEW_STATE=reference CALDOVA_EXPECTED_PREVIEW_STATE=reference \
    CALDOVA_DATA_DIR=/app/data/artifacts/development CALDOVA_STATIC_DIR=/app/static \
    TMPDIR=/app/.runtime
COPY data/pipeline/ data/pipeline/
COPY data/fixtures/research-data.json data/fixtures/research-data.json
COPY data/artifacts/development/ data/artifacts/development/
COPY src/research-portal/backend/ src/research-portal/backend/
COPY src/research-portal/frontend/ src/research-portal/frontend/
COPY candidate-provenance.json candidate-provenance.json
RUN pip install --no-cache-dir -r src/research-portal/backend/requirements.txt \
    && pip check \
    && python -m data.pipeline.validate_dataset --manifest data/artifacts/development/data-manifest.json \
    && useradd --uid 10001 --create-home caldova \
    && mkdir .runtime && chown caldova:caldova .runtime \
    && chmod -R a-w data src candidate-provenance.json
COPY --from=frontend /web/dist/ /app/static/
USER caldova
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3)"
CMD ["uvicorn", "app:app", "--app-dir", "src/research-portal/backend", "--host", "0.0.0.0", "--port", "8080"]

FROM runtime AS validation
COPY tests/test_research.py tests/test_research.py
COPY tests/test_frozen_public_research.py tests/test_frozen_public_research.py
COPY src/workers/frozen_contract.py src/workers/frozen_contract.py
COPY src/developer-image/stage_candidate.py src/developer-image/stage_candidate.py
RUN python src/developer-image/stage_candidate.py --validate-container

FROM runtime AS candidate
COPY --from=validation /app/.runtime/candidate-validation.json /app/candidate-validation.json
