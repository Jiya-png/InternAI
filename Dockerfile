# InternAI - single container: React build served by FastAPI (one URL, one port).
# Good for Render / Railway / any Docker host.
#   docker build -t internai . && docker run -p 8000:8000 internai   ->  http://localhost:8000

# ---- 1) build the frontend ---------------------------------------------------
FROM node:20-alpine AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

# ---- 2) backend + trained models ----------------------------------------------
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
ARG EMBEDDINGS=auto
ENV INTERNAI_EMBEDDINGS=${EMBEDDINGS} INTERNAI_FRONTEND_DIST=/app/frontend/dist
WORKDIR /app/backend
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu
COPY backend/requirements.txt .
RUN pip install -r requirements.txt && python -m spacy download en_core_web_sm
COPY backend/ .
RUN python -m app.ml.build_courses && python -m app.ml.generate_data && python -m app.ml.train --fast
COPY --from=web /web/dist /app/frontend/dist

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
