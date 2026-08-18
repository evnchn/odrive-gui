FROM zauberzeug/nicegui:latest

RUN apt-get update && apt-get install -y libusb-1.0-0 libusb-1.0-0-dev && rm -rf /var/lib/apt/lists/*

# install the exact locked dependency set with uv (reproducible: pins come from uv.lock).
# The base image runs the app with /opt/venv/bin/python (its CMD and PATH), so install
# into that interpreter explicitly: `--system` would target /usr/local/bin/python3 instead
# and the container would die at `import odrive`.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-dev --no-emit-project -o /tmp/requirements.txt \
    && uv pip install --python /opt/venv/bin/python --no-cache -r /tmp/requirements.txt

COPY src .
