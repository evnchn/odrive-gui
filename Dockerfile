FROM zauberzeug/nicegui:latest

RUN apt-get update && apt-get install -y libusb-1.0-0 libusb-1.0-0-dev && rm -rf /var/lib/apt/lists/*

# install the exact locked dependency set with uv (reproducible: pins come from uv.lock)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-dev --no-emit-project -o /tmp/requirements.txt \
    && uv pip install --system --no-cache -r /tmp/requirements.txt

COPY src .
