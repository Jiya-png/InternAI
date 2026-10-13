# InternAI backend (API only). Build from the repo root:
#   docker build -f backend/Dockerfile -t internai-api .
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
# auto = sentence-transformers if it can be downloaded, else TF-IDF.
# Use --build-arg EMBEDDINGS=tfidf for small (512 MB RAM) hosts.
ARG EMBEDDINGS=auto
ENV INTERNAI_EMBEDDINGS=${EMBEDDINGS}

WORKDIR /app/backend
# CPU-only PyTorch first (avoids multi-GB CUDA wheels)
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu
COPY backend/requirements.txt .
RUN pip install -r requirements.txt && python -m spacy download en_core_web_sm

COPY backend/ .
# Build the catalog, generate synthetic data and train the models inside the image
RUN python -m app.ml.build_courses \
 && python -m app.ml.validate_catalog \
 && python -m app.ml.generate_data \
 && python -m app.ml.train --fast

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
