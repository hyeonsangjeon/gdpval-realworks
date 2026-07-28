# Candidate-only professional-work substrate for Agentic Sandbox V2 Phase 1B.
# No mutable default is allowed: the caller must provide the exact parent lock.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}

ARG SOURCE_REVISION
ARG CAPABILITY_MANIFEST_SHA256
ARG PARENT_MANIFEST_DIGEST

LABEL org.opencontainers.image.title="gdpval-agentic-v2-professional-work-candidate" \
      org.opencontainers.image.description="Model-free Phase 1B professional-work candidate; execution activation disabled" \
      org.opencontainers.image.source="https://github.com/hyeonsangjeon/gdpval-realworks" \
      org.opencontainers.image.revision="${SOURCE_REVISION}" \
      org.opencontainers.image.base.digest="${PARENT_MANIFEST_DIGEST}" \
      io.gdpval.agentic-v2.substrate="professional-work-v1" \
      io.gdpval.agentic-v2.foundation-only="true" \
      io.gdpval.agentic-v2.production-activation="disabled" \
      io.gdpval.agentic-v2.capability-manifest-sha256="${CAPABILITY_MANIFEST_SHA256}"

USER 0:0

ENV DEBIAN_FRONTEND=noninteractive \
    HOME=/work/.home \
    TMPDIR=/work/.tmp \
    XDG_CACHE_HOME=/work/.cache \
    XDG_CONFIG_HOME=/work/.config \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLCONFIGDIR=/work/.cache/matplotlib \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

RUN mkdir -p /work/.home /work/.tmp /work/.cache /work/.config \
    && chmod 0700 /work /work/.home /work/.tmp /work/.cache /work/.config

COPY sandbox/v2/debian-extra.lock /opt/gdpval/v2/debian-extra.lock
RUN apt-get update -qq \
    && xargs -r apt-get install -y --no-install-recommends \
        < /opt/gdpval/v2/debian-extra.lock \
    && while IFS= read -r package; do \
         test "$(dpkg-query -W -f='${Version}' "${package%%=*}")" = "${package#*=}"; \
       done < /opt/gdpval/v2/debian-extra.lock \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY sandbox/v2/python-extra.lock /opt/gdpval/v2/python-extra.lock
RUN python -m pip install --no-deps --require-hashes \
      -r /opt/gdpval/v2/python-extra.lock

COPY core/agentic_v2_substrate.py /opt/gdpval/v2/agentic_v2_substrate.py
COPY sandbox/agentic_v2_capabilities.json /opt/gdpval/v2/capabilities.json
COPY sandbox/v2/image_probe.py /opt/gdpval/v2/image_probe.py
COPY sandbox/v2/effective_sbom.py /opt/gdpval/v2/effective_sbom.py
COPY sandbox/v2/disabled_entrypoint.py /opt/gdpval/v2/disabled_entrypoint.py

RUN if ! getent group 65532 >/dev/null; then \
            groupadd --gid 65532 agentic-v2; \
        fi \
        && if ! getent passwd 65532 >/dev/null; then \
            useradd --uid 65532 --gid 65532 --no-create-home \
                --home-dir /work/.home agentic-v2; \
        fi \
    && mkdir -p /work/.home /work/.tmp /work/.cache /work/.config \
    && chown -R 65532:65532 /work \
    && chmod 0700 /work /work/.home /work/.tmp /work/.cache /work/.config \
    && chmod -R a-w /opt/gdpval \
    && find / -xdev -type f \( -perm -4000 -o -perm -2000 \) \
       -exec chmod a-s {} +

USER 65532:65532
WORKDIR /work

ENTRYPOINT ["python", "-I", "-B", "/opt/gdpval/v2/disabled_entrypoint.py"]