FROM zauberzeug/nicegui:2.11.1

RUN apt-get update \
    && apt-get install -y --no-install-recommends libusb-1.0-0 libusb-1.0-0-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --no-cache-dir odrive matplotlib

COPY src .
