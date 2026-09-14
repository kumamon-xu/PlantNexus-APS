FROM docker:27.5.1-dind@sha256:f649ef046008ca7f926a2571c32b0ac22e5c59eb61b959617f9acc2a4c638cf5
# Build-side system tools only; no Python/development environment or APS payload.
RUN apk add --no-cache coreutils=9.5-r2 findutils=4.10.0-r0 gawk=5.3.1-r0 curl=8.14.1-r2 jq=1.7.1-r0 bash=5.2.37-r0 \
    && ! command -v python && ! command -v python3
ENV DOCKER_TLS_CERTDIR=""
