FROM python:3.11-slim

WORKDIR /app

# System deps for psycopg2 + apply latest Debian security patches.
# `apt-get upgrade -y` pulls the most recent CVE-patched versions of
# every base-image package — significantly reduces the Trivy-image
# HIGH/CRITICAL count without changing the base tag.
RUN apt-get update && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
        build-essential libpq-dev git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install CPU-only torch first to avoid pulling the 2 GB GPU build
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as non-root. Mitigates container escape blast radius and satisfies
# CIS Docker Benchmark 4.1 / Semgrep dockerfile.security.missing-user.
RUN useradd --create-home --shell /usr/sbin/nologin --uid 1001 app \
    && chown -R app:app /app
USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
