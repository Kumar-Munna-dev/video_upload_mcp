# Google Cloud Run image for the YouTube + Instagram + Facebook + voice server.
# Cloud Build builds it from GitHub on every push to main. No secrets inside: they are Cloud Run environment variables.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HTTP2=1

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# only the code (never tokens, keys or videos)
COPY youtube_mcp.py social.py sarvam_voice.py ./

# Cloud Run sets PORT (8080)
CMD ["python", "youtube_mcp.py", "http"]
