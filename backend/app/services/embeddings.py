"""
Sentence embeddings for semantic similarity (resume profile vs job description).

Primary backend : sentence-transformers ``all-MiniLM-L6-v2`` (384-d, CPU friendly).
Fallback backend: TF-IDF + TruncatedSVD (used automatically if the transformer
                  model cannot be downloaded/loaded, or when
                  INTERNAI_EMBEDDINGS=tfidf).

All vectors are L2-normalised so cosine similarity = dot product.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol

import joblib
import numpy as np

from app.config import ARTIFACTS_DIR, EMBEDDING_MODEL, EMBEDDINGS_BACKEND

log = logging.getLogger(__name__)
TFIDF_EMBEDDER_PATH: Path = ARTIFACTS_DIR / "tfidf_embedder.joblib"


class Embedder(Protocol):
    backend: str

    def encode(self, texts: list[str]) -> np.ndarray: ...


def _normalise(x: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(x, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (x / norms).astype(np.float32)


class STEmbedder:
    backend = "sentence-transformers"

    def __init__(self, model_name: str = EMBEDDING_MODEL) -> None:
        from sentence_transformers import SentenceTransformer  # heavy import, lazy

        self.model = SentenceTransformer(model_name, device="cpu")

    def encode(self, texts: list[str]) -> np.ndarray:
        vecs = self.model.encode(texts, batch_size=64, show_progress_bar=len(texts) > 500,
                                 convert_to_numpy=True, normalize_embeddings=True)
        return vecs.astype(np.float32)


class TfidfEmbedder:
    """Light-weight fallback: TF-IDF (word 1-2 grams) -> 256-d LSA space."""

    backend = "tfidf-lsa"

    def __init__(self, vectorizer=None, svd=None) -> None:
        self.vectorizer = vectorizer
        self.svd = svd

    def fit(self, corpus: list[str], dims: int = 192) -> "TfidfEmbedder":
        from sklearn.decomposition import TruncatedSVD
        from sklearn.feature_extraction.text import TfidfVectorizer

        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1, max_features=15000,
                                          sublinear_tf=True, stop_words="english")
        x = self.vectorizer.fit_transform(corpus)
        dims = max(2, min(dims, x.shape[1] - 1, x.shape[0] - 1))
        self.svd = TruncatedSVD(n_components=dims, random_state=42).fit(x)
        return self

    def encode(self, texts: list[str]) -> np.ndarray:
        if self.vectorizer is None or self.svd is None:
            raise RuntimeError("TfidfEmbedder is not fitted")
        return _normalise(self.svd.transform(self.vectorizer.transform(texts)))

    def save(self, path: Path = TFIDF_EMBEDDER_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"vectorizer": self.vectorizer, "svd": self.svd}, path)

    @classmethod
    def load(cls, path: Path = TFIDF_EMBEDDER_PATH) -> "TfidfEmbedder":
        d = joblib.load(path)
        return cls(d["vectorizer"], d["svd"])


def load_embedder(preferred: str | None = None, fallback_corpus: list[str] | None = None) -> Embedder:
    """
    Return the requested backend, falling back to TF-IDF if needed.

    preferred: "sentence-transformers", "tfidf-lsa" or None/"auto".
    fallback_corpus: texts to fit a TF-IDF embedder on if no saved one exists.
    """
    preferred = preferred or EMBEDDINGS_BACKEND
    if preferred in ("auto", "sentence-transformers", "st") and EMBEDDINGS_BACKEND != "tfidf":
        try:
            emb = STEmbedder()
            log.info("Using sentence-transformers embeddings (%s)", EMBEDDING_MODEL)
            return emb
        except Exception as exc:  # no internet / not installed / low memory
            log.warning("sentence-transformers unavailable (%s) -> using TF-IDF embeddings", exc)
    if TFIDF_EMBEDDER_PATH.exists():
        return TfidfEmbedder.load()
    if not fallback_corpus:
        raise RuntimeError("No embedding backend available and no corpus to fit a TF-IDF fallback")
    return TfidfEmbedder().fit(fallback_corpus)


def cosine(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Cosine similarity between rows of a (n,d) and rows of b (m,d) -> (n,m)."""
    return a @ b.T
