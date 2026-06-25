FROM zauberzeug/nicegui:3.13.0

RUN apt-get update \
    && apt-get install -y --no-install-recommends libusb-1.0-0 libusb-1.0-0-dev \
    && rm -rf /var/lib/apt/lists/*

# install the dependency set from pyproject.toml (single source of truth)
COPY pyproject.toml README.md ./
RUN python3 -m pip install --no-cache-dir .

COPY src .
