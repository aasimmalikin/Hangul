FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml ./
COPY src ./src
RUN pip install .

FROM python:3.12-slim AS runtime

RUN useradd --create-home --uid 10001 appuser
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

COPY --from=builder /opt/venv /opt/venv

USER appuser
WORKDIR /home/appuser
EXPOSE 8000

CMD ["uvicorn", "harness.api.app:app", "--host", "0.0.0.0", "--port", "8000"]