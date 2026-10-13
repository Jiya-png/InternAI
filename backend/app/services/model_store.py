"""
Loads trained artifacts once and offers simple prediction helpers.

Artifacts (written by ml/train.py into app/ml/artifacts/):
    role_classifier.joblib   Pipeline(ResumeFeaturizer -> classifier with predict_proba)
    match_regressor.joblib   regressor over services.features.MATCH_FEATURES
    tfidf_embedder.joblib    fallback embedder (always saved)
    metadata.json            metrics, chosen models, embedding backend, versions

If artifacts are missing the app still works with the transparent heuristic
formula (services.features.heuristic_match) and TF-IDF similarity.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import joblib
import numpy as np

from app.config import ARTIFACTS_DIR
from app.services.catalog import Role, load_roles
from app.services.embeddings import Embedder, load_embedder
from app.services.features import MATCH_FEATURES, heuristic_match
from app.services.role_classifier import to_frame

log = logging.getLogger(__name__)


def role_document(role: Role) -> str:
    """Text that represents a role for embeddings."""
    req = ", ".join(rs.skill for rs in sorted(role.required_skills, key=lambda r: -r.weight))
    return f"{role.title}. {role.description} Key skills: {req}."


@dataclass
class ModelBundle:
    classifier: Any | None
    regressor: Any | None
    embedder: Embedder
    role_ids: list[str]
    role_matrix: np.ndarray            # (n_roles, d) normalised embeddings
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def trained(self) -> bool:
        return self.classifier is not None and self.regressor is not None

    # ---- predictions ------------------------------------------------------ #
    def role_probabilities(self, text: str, skills: list[str]) -> dict[str, float]:
        if self.classifier is None:
            return {}
        probs = self.classifier.predict_proba(to_frame(text, skills))[0]
        return {str(c): float(p) for c, p in zip(self.classifier.classes_, probs)}

    def role_probabilities_many(self, texts: list[str], skills: list[list[str]]) -> np.ndarray:
        """(n, n_roles) in self.role_ids order."""
        import pandas as pd

        if self.classifier is None:
            return np.zeros((len(texts), len(self.role_ids)))
        p = self.classifier.predict_proba(pd.DataFrame({"text": texts, "skills": skills}))
        idx = [list(self.classifier.classes_).index(r) for r in self.role_ids]
        return p[:, idx]

    def similarities(self, profile_texts: list[str]) -> np.ndarray:
        """(n, n_roles) cosine similarity, clipped to [0, 1]."""
        vecs = self.embedder.encode(profile_texts)
        return np.clip(vecs @ self.role_matrix.T, 0.0, 1.0)

    def predict_match(self, rows: list[dict[str, float]]) -> np.ndarray:
        if self.regressor is None:
            return np.array([heuristic_match(r) for r in rows])
        x = np.array([[r[f] for f in MATCH_FEATURES] for r in rows], dtype=np.float64)
        return np.clip(self.regressor.predict(x), 0.0, 100.0)


def build_role_matrix(embedder: Embedder) -> tuple[list[str], np.ndarray]:
    roles = list(load_roles().values())
    return [r.id for r in roles], embedder.encode([role_document(r) for r in roles])


@lru_cache(maxsize=1)
def get_models() -> ModelBundle:
    meta_path = ARTIFACTS_DIR / "metadata.json"
    metadata: dict[str, Any] = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    clf = reg = None
    try:
        clf = joblib.load(ARTIFACTS_DIR / "role_classifier.joblib")
        reg = joblib.load(ARTIFACTS_DIR / "match_regressor.joblib")
    except FileNotFoundError:
        log.warning("Trained models not found in %s - using heuristic scoring. Run: python -m app.ml.train",
                    ARTIFACTS_DIR)
    except Exception as exc:  # e.g. scikit-learn version mismatch
        log.error("Could not load models (%s) - using heuristic scoring. Re-run training.", exc)
        clf = reg = None
    corpus = [role_document(r) for r in load_roles().values()]
    embedder = load_embedder(metadata.get("embedding_backend"), fallback_corpus=corpus)
    if metadata.get("embedding_backend") and metadata["embedding_backend"] != embedder.backend:
        log.warning("Model was trained with %s embeddings but %s is in use; scores may shift slightly.",
                    metadata["embedding_backend"], embedder.backend)
    role_ids, matrix = build_role_matrix(embedder)
    metadata["embedding_backend_in_use"] = embedder.backend
    return ModelBundle(clf, reg, embedder, role_ids, matrix, metadata)
