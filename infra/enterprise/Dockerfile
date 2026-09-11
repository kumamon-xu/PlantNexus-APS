FROM python:3.12.13-slim-bookworm@sha256:6e13e65c55e33adf203d77ee371cf8bf5d81bd4902ef07565721f46bf44917af AS install

WORKDIR /install
COPY requirements/ ./requirements/
COPY wheels/ ./wheels/
RUN python -m venv /opt/venv \
    && /opt/venv/bin/python -m pip install --no-cache-dir --only-binary=:all: --require-hashes -r requirements/runtime-requirements.lock \
    && /opt/venv/bin/python -m pip install --no-cache-dir --no-deps wheels/*.whl \
    && /opt/venv/bin/python -m pip check \
    && /opt/venv/bin/python -m pip uninstall -y pip

FROM python:3.12.13-slim-bookworm@sha256:6e13e65c55e33adf203d77ee371cf8bf5d81bd4902ef07565721f46bf44917af

ARG APS_PACKAGING_SHA
ARG APS_CREATED
LABEL org.opencontainers.image.title="PlantNexus APS Runtime" \
    org.opencontainers.image.version="0.1.0" \
    org.opencontainers.image.revision="${APS_PACKAGING_SHA}" \
    org.opencontainers.image.created="${APS_CREATED}" \
    org.opencontainers.image.base.name="python:3.12.13-slim-bookworm" \
    org.opencontainers.image.base.digest="sha256:6e13e65c55e33adf203d77ee371cf8bf5d81bd4902ef07565721f46bf44917af" \
    io.plantnexus.aps.application.version="0.0.0" \
    io.plantnexus.aps.core.version="0.0.0" \
    io.plantnexus.aps.schema.version="2.10.0" \
    io.plantnexus.aps.source-runtime-revision="39149091859b35b1303002a237a3cf1344572773" \
    io.plantnexus.aps.source-runtime-sha256="7c90ba63b0ba950eb256488c5647e9463760eb01c720b69a744bff1a3ce742fc" \
    io.plantnexus.aps.release-channel="unsigned-internal"

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates=20250419~deb12u1 libpcre2-8-0=10.42-1+deb12u1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 plantnexus \
    && python -m pip uninstall -y pip \
    && python -c "import shutil; shutil.rmtree('/usr/local/lib/python3.12/ensurepip')"
COPY --from=install /opt/venv /opt/venv
COPY runtime/ /opt/plantnexus/
COPY metadata/ /opt/plantnexus/metadata/
COPY requirements/ /opt/plantnexus/requirements/
COPY image_probe.py /opt/plantnexus/image_probe.py
ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /opt/plantnexus
USER 10001:10001
CMD ["uvicorn", "app.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
