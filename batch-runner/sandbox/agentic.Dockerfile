# Hardened task/verifier image for execution.mode=agentic_sandbox.
ARG BASE_IMAGE=gdpval-sandbox:latest
FROM ${BASE_IMAGE}

USER 0:0

RUN apt-get update -qq \
    && apt-get install -y --no-install-recommends libseccomp2 \
    && groupadd --gid 65532 agentic \
    && useradd --uid 65532 --gid 65532 --no-create-home --home-dir /work/.home agentic \
    && rm -rf /var/lib/apt/lists/*

RUN apt-get update -qq \
    && apt-get purge -y --auto-remove \
        build-essential gfortran gcc g++ cpp make cmake binutils dpkg-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY core /opt/gdpval/core
COPY sandbox/agentic-capabilities.json /opt/gdpval/agentic-capabilities.json
COPY sandbox/agentic_image_prepare.py /opt/gdpval/agentic_image_prepare.py
COPY sandbox/agentic_image_audit.py /opt/gdpval/agentic_image_audit.py
COPY sandbox/agentic_sbom.py /opt/gdpval/agentic_sbom.py

ENV PYTHONPATH=/opt/gdpval \
    HOME=/work/.home \
    TMPDIR=/work/.tmp \
    XDG_CACHE_HOME=/work/.cache \
    XDG_CONFIG_HOME=/work/.config \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLCONFIGDIR=/work/.cache/matplotlib \
    FONTCONFIG_PATH=/etc/fonts

# Generated code is additionally constrained by an in-process seccomp filter.
# Removing package/download/build entrypoints keeps accidental invocation from
# trusted helper processes fail-closed as well.
RUN python /opt/gdpval/agentic_image_prepare.py \
    && rm -f /opt/gdpval/agentic_image_prepare.py

RUN python /opt/gdpval/agentic_sbom.py > /opt/gdpval/agentic-sbom.spdx.json \
    && chmod 0444 /opt/gdpval/agentic-sbom.spdx.json

RUN mkdir -p /work /inputs /verify-work \
    && chown 65532:65532 /work /verify-work \
    && chmod 0700 /work /verify-work \
    && chmod -R a-w /opt/gdpval

# This must be the final RUN instruction: Docker's shell-form RUN needs /bin/sh.
RUN find / -xdev -type f \( -perm -4000 -o -perm -2000 \) -exec chmod a-s {} + \
    && find /usr/local/bin /usr/bin /bin -xdev -type f -perm -0002 -exec chmod o-w {} + \
    && rm -f /bin/sh /bin/bash /usr/bin/dash /usr/bin/bash

USER 65532:65532
WORKDIR /work

ENTRYPOINT ["python", "-I", "-B", "-u"]
CMD ["/opt/gdpval/core/agentic_idle.py"]