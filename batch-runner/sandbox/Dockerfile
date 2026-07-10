# GDPVal Sandbox Image — skill-aware, multimodal code-execution container.
#
# This image is the execution backend for `execution.mode: sandbox`. It bakes in
# the same Python dependencies the CI host installs (batch-runner/requirements.txt)
# plus the system libraries those packages need (ffmpeg, poppler, tesseract,
# libreoffice, graphviz, GDAL/GEOS, weasyprint stack, …) so that LLM-generated
# `solution.py` runs identically whether it touches audio, video, documents,
# images, geo data, or ML.
#
# Build (from batch-runner/):   bash sandbox/build.sh
# Pin Python to 3.11 to match the GitHub Actions runner.
FROM python:3.11-slim-bookworm

LABEL org.opencontainers.image.title="gdpval-sandbox" \
      org.opencontainers.image.description="Skill-aware multimodal sandbox for GDPVal solving" \
      org.opencontainers.image.source="https://github.com/hyeonsangjeon/gdpval-realworks"

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    MPLBACKEND=Agg

# ── System libraries ────────────────────────────────────────────────────────
# Grouped by the Python packages that require them.
RUN apt-get update -qq && apt-get install -y --no-install-recommends \
      # build toolchain (pygraphviz, h5py, native wheels)
      build-essential pkg-config gfortran \
      # audio / video  (librosa, soundfile, pydub, moviepy, av, ffmpeg-python)
      ffmpeg libsndfile1 \
      # opencv runtime
      libgl1 libglib2.0-0 \
      # documents / pdf  (pdfplumber, pdf2image, camelot, tabula, pypandoc)
      poppler-utils pandoc default-jre-headless \
      # office conversion (docx/pptx/xlsx ↔ pdf)
      libreoffice \
      # ocr / barcodes  (pytesseract, pyzbar)
      tesseract-ocr libzbar0 \
      # html → pdf/png  (weasyprint, pdfkit, imgkit, cairosvg)
      libcairo2 libcairo2-dev libpango-1.0-0 libpangocairo-1.0-0 \
      libgdk-pixbuf-2.0-0 libffi-dev wkhtmltopdf \
      # graphs  (pygraphviz, pydot)
      graphviz libgraphviz-dev \
      # geo  (geopandas, fiona, rasterio, shapely, pyproj)
      gdal-bin libgdal-dev libgeos-dev libproj-dev proj-bin proj-data \
      # scientific i/o  (h5py, tables)
      libhdf5-dev \
      # xml / lxml, pillow
      libxml2-dev libxslt1-dev libjpeg-dev zlib1g-dev \
      # tts  (pyttsx3)
      espeak-ng \
      # fonts for rendered deliverables
      fonts-dejavu fonts-liberation fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# ── Python dependencies ─────────────────────────────────────────────────────
# Copy only requirements first to maximize Docker layer caching.
COPY requirements.txt /tmp/requirements.txt
RUN python -m pip install --upgrade pip setuptools wheel \
    && pip install -r /tmp/requirements.txt \
    && rm -f /tmp/requirements.txt

# ── Skills (baked-in fallback) ──────────────────────────────────────────────
# The runner also bind-mounts skills/ into the work dir, but baking them here
# guarantees `import skills` works even if the mount is skipped.
COPY skills /opt/gdpval/skills
ENV PYTHONPATH=/opt/gdpval

# ── Working directory ───────────────────────────────────────────────────────
# The runner bind-mounts a per-task tmpdir onto /work and runs solution.py here.
RUN mkdir -p /work
WORKDIR /work

CMD ["python", "-u", "solution.py"]
