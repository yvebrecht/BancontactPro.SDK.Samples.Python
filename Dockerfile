# syntax=docker/dockerfile:1
# The package is not published yet and the sample installs the sister folder ../BancontactPro.Python, so the build context is the
# folder that holds both repositories. From this folder: docker compose up --build (see docker-compose.yml).

FROM python:3.13-slim
WORKDIR /work

ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONUNBUFFERED=1

# The library, installed from the sister folder instead of the editable "-e ../BancontactPro.Python" line of requirements.txt.
COPY BancontactPro.Python/ BancontactPro.Python/
COPY BancontactPro.SDK.Samples.Python/requirements.txt BancontactPro.SDK.Samples.Python/
RUN grep -v '^-e' BancontactPro.SDK.Samples.Python/requirements.txt > /tmp/requirements.txt \
    && pip install /work/BancontactPro.Python -r /tmp/requirements.txt

COPY BancontactPro.SDK.Samples.Python/run.py BancontactPro.SDK.Samples.Python/run.py
COPY BancontactPro.SDK.Samples.Python/sample_web/ BancontactPro.SDK.Samples.Python/sample_web/
COPY BancontactPro.SDK.Samples.Python/public/ BancontactPro.SDK.Samples.Python/public/

WORKDIR /work/BancontactPro.SDK.Samples.Python
USER nobody
ENV HOST=0.0.0.0 PORT=8080
EXPOSE 8080
CMD ["python", "run.py"]
