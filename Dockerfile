FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    JOBCOMPASS_DB=/app/data/shared.sqlite \
    JOBCOMPASS_PUBLIC=1
WORKDIR /app
COPY requirements.txt requirements-server.txt ./
RUN python -m pip install --no-cache-dir -r requirements-server.txt \
    && groupadd --gid 10001 jobcompass \
    && useradd --uid 10001 --gid jobcompass --no-create-home --shell /usr/sbin/nologin jobcompass

# Explicit source/data allowlist: no workstation .env, resume DB, raw archives or model weights.
COPY main.py LICENSE ./
COPY jobcompass/ ./jobcompass/
COPY data/demo_jobs.json data/demo_resume.txt data/import_template.csv ./data/
COPY data/benchmark/jobsdb_20260928.json.gz data/benchmark/jobsdb_20260928.manifest.json ./data/benchmark/
COPY deploy/healthcheck.py deploy/build_research_index.py ./deploy/
RUN mkdir -p /app/data/private && chown -R 10001:10001 /app/data
USER 10001:10001
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 CMD ["python", "deploy/healthcheck.py"]
CMD ["gunicorn", "--workers", "1", "--threads", "8", "--bind", "0.0.0.0:8765", "--timeout", "120", "--no-control-socket", "--access-logfile", "-", "--error-logfile", "-", "jobcompass.wsgi:application"]
