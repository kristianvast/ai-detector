ARG TARGETARCH
FROM ultralytics/ultralytics:latest AS runtime-amd64
FROM ultralytics/ultralytics:latest-nvidia-arm64 AS runtime-arm64
FROM runtime-${TARGETARCH} AS runtime

# Install uv for fast package installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy application files
COPY . /app

# Write version file with REF_NAME (defaults to "main" if not provided)
ARG REF_NAME=main
RUN echo "REF_NAME = \"${REF_NAME}\"" > /app/src/aidetector/version.py

# Install the application directly into the ultralytics Python environment
# --break-system-packages is needed because Debian marks system Python as externally managed
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --break-system-packages .

# Setup a non-root user
RUN groupadd --system --gid 999 nonroot \
    && useradd --system --gid 999 --uid 999 --create-home nonroot

# Give nonroot user write access to ultralytics weights directory (for model downloads)
RUN mkdir -p /ultralytics/weights && chown -R nonroot:nonroot /ultralytics

# Change ownership of the app directory
RUN chown -R nonroot:nonroot /app

# Use the non-root user to run our application
USER nonroot

# Run the application
CMD ["python3", "src/aidetector/__init__.py"]
