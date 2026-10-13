"""
Feature builder for the role classifier: TF-IDF of the resume text (1-2 grams)
concatenated with a multi-hot vector of extracted canonical skills.

It is a regular scikit-learn transformer, so it is saved inside the classifier
Pipeline with joblib and reused unchanged at inference time.
"""
from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.feature_extraction.text import TfidfVectorizer

from app.services.catalog import load_skills


class ResumeFeaturizer(BaseEstimator, TransformerMixin):
    """
    Input : DataFrame with columns ``text`` (str) and ``skills`` (list[str]).
    Output: sparse matrix [tfidf | skill_weight * multi_hot_skills]
    """

    def __init__(self, max_features: int = 20000, skill_weight: float = 1.0, min_df: int = 2) -> None:
        self.max_features = max_features
        self.skill_weight = skill_weight
        self.min_df = min_df

    def fit(self, X: pd.DataFrame, y: Sequence | None = None) -> "ResumeFeaturizer":
        self.tfidf_ = TfidfVectorizer(ngram_range=(1, 2), max_features=self.max_features, min_df=self.min_df,
                                      sublinear_tf=True, strip_accents="unicode", lowercase=True)
        self.tfidf_.fit(X["text"].tolist())
        self.skill_index_ = {name: i for i, name in enumerate(load_skills())}
        return self

    def _multi_hot(self, skills_col: Sequence[Sequence[str]]) -> sparse.csr_matrix:
        rows, cols = [], []
        for r, skills in enumerate(skills_col):
            for s in set(skills):
                j = self.skill_index_.get(s)
                if j is not None:
                    rows.append(r)
                    cols.append(j)
        data = np.full(len(rows), self.skill_weight, dtype=np.float32)
        return sparse.csr_matrix((data, (rows, cols)), shape=(len(skills_col), len(self.skill_index_)))

    def transform(self, X: pd.DataFrame) -> sparse.csr_matrix:
        t = self.tfidf_.transform(X["text"].tolist())
        s = self._multi_hot(X["skills"].tolist())
        return sparse.hstack([t, s], format="csr")


def to_frame(text: str, skills: Sequence[str]) -> pd.DataFrame:
    """One-row input frame for inference."""
    return pd.DataFrame({"text": [text], "skills": [list(skills)]})
