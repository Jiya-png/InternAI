"""
Step 4 - Train and evaluate all models.

    a) Role classifier : TF-IDF(1-2 grams) + skill multi-hot  ->  LogisticRegression
                         (compared with LinearSVC [calibrated] and RandomForest)
    b) Semantic sim.   : sentence-transformer (all-MiniLM-L6-v2) embeddings of the resume
                         profile vs each role description (cosine). TF-IDF/LSA fallback.
    c) Match regressor : HistGradientBoosting (monotonic) vs Ridge over
                         [weighted overlap, % required matched, nice-to-have ratio,
                          cosine similarity, classifier probability, experience fit]

Generalisation check: train on resume styles 0-3, validate on the *unseen*
styles 4-5 (different headings, bullets, date formats, no skills section).
After evaluation the chosen models are re-fitted on all data and saved.

Run from ``backend`` (after generate_data):
    python -m app.ml.train            # full
    python -m app.ml.train --fast     # skip RandomForest comparison
"""
from __future__ import annotations

import argparse
import json
import platform
import time
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestClassifier
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from app.config import ARTIFACTS_DIR, DATA_DIR, RANDOM_SEED
from app.services.catalog import load_roles
from app.services.embeddings import TfidfEmbedder, load_embedder
from app.services.features import MATCH_FEATURES, profile_text, rule_features
from app.services.model_store import build_role_matrix, role_document
from app.services.parser import parse_text
from app.services.role_classifier import ResumeFeaturizer

VAL_STYLES = {4, 5}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #
def load_and_parse() -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_csv(DATA_DIR / "synthetic_resumes.csv")
    pairs = pd.read_csv(DATA_DIR / "match_pairs.csv")
    log(f"Parsing {len(df)} synthetic resumes with the real parser (so features match inference)...")
    skills, years, profiles = [], [], []
    for text in df["text"]:
        p = parse_text(text)
        skills.append(p["skills"])
        years.append(p["years_of_experience"])
        profiles.append(profile_text(p["skills"], [e["title"] for e in p["experience"] if e["title"]],
                                     [pr["title"] for pr in p["projects"]], p["summary"]))
    df["parsed_skills"] = skills
    df["parsed_years"] = years
    df["profile"] = profiles
    df["is_val"] = df["style_id"].isin(VAL_STYLES)
    return df, pairs


def clf_frame(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({"text": df["text"].values, "skills": df["parsed_skills"].values})


# --------------------------------------------------------------------------- #
# a) Role classifier
# --------------------------------------------------------------------------- #
def candidate_classifiers(fast: bool) -> dict[str, Pipeline]:
    cands = {
        "LogisticRegression": Pipeline([
            ("features", ResumeFeaturizer()),
            ("clf", LogisticRegression(C=8.0, max_iter=3000)),
        ]),
        "LinearSVC (calibrated)": Pipeline([
            ("features", ResumeFeaturizer()),
            ("clf", CalibratedClassifierCV(LinearSVC(C=0.5), cv=3)),
        ]),
    }
    if not fast:
        cands["RandomForest"] = Pipeline([
            ("features", ResumeFeaturizer(max_features=8000)),
            ("clf", RandomForestClassifier(n_estimators=250, max_features="sqrt", n_jobs=-1,
                                           random_state=RANDOM_SEED, class_weight="balanced")),
        ])
    return cands


def train_classifier(df: pd.DataFrame, fast: bool) -> tuple[str, Pipeline, dict]:
    tr, va = df[~df.is_val], df[df.is_val]
    Xtr, Xva = clf_frame(tr), clf_frame(va)
    results: dict[str, dict] = {}
    fitted: dict[str, Pipeline] = {}
    for name, pipe in candidate_classifiers(fast).items():
        t0 = time.time()
        pipe.fit(Xtr, tr["role_id"])
        pred = pipe.predict(Xva)
        results[name] = {
            "accuracy": round(accuracy_score(va["role_id"], pred), 4),
            "macro_f1": round(f1_score(va["role_id"], pred, average="macro"), 4),
            "train_seconds": round(time.time() - t0, 1),
        }
        fitted[name] = pipe
        log(f"  {name:<24} acc={results[name]['accuracy']:.4f}  macro-F1={results[name]['macro_f1']:.4f}"
            f"  ({results[name]['train_seconds']}s)")
    best = max(results, key=lambda k: results[k]["macro_f1"])
    # Prefer Logistic Regression (smooth, well-calibrated probabilities, small file)
    # unless another model is clearly better (> 1 point of macro-F1).
    if best != "LogisticRegression" and results[best]["macro_f1"] - results["LogisticRegression"]["macro_f1"] <= 0.01:
        log(f"{best} is only marginally better -> keeping LogisticRegression")
        best = "LogisticRegression"
    log(f"Chosen classifier: {best}")

    # confusion matrix + per-class F1 for the best model
    best_pipe = fitted[best]
    pred = best_pipe.predict(Xva)
    labels = list(load_roles())
    cm = confusion_matrix(va["role_id"], pred, labels=labels)
    pd.DataFrame(cm, index=labels, columns=labels).to_csv(ARTIFACTS_DIR / "confusion_matrix.csv")
    per_class = f1_score(va["role_id"], pred, labels=labels, average=None)
    _plot_confusion(cm, labels)
    # hard cases
    hard = {}
    for case in ("normal", "hybrid", "weak"):
        m = (va["case_type"] == case).values
        if m.any():
            hard[case] = round(accuracy_score(va["role_id"].values[m], pred[m]), 4)
    report = {
        "comparison": results,
        "chosen": best,
        "per_class_f1": {l: round(float(f), 4) for l, f in zip(labels, per_class)},
        "accuracy_by_case_type": hard,
        "most_confused": _most_confused(cm, labels),
    }
    return best, best_pipe, report


def _most_confused(cm: np.ndarray, labels: list[str], k: int = 5) -> list[dict]:
    off = cm.copy()
    np.fill_diagonal(off, 0)
    idx = np.dstack(np.unravel_index(np.argsort(-off.ravel()), off.shape))[0][:k]
    return [{"true": labels[i], "predicted": labels[j], "count": int(off[i, j])} for i, j in idx if off[i, j] > 0]


def _plot_confusion(cm: np.ndarray, labels: list[str]) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    fig, ax = plt.subplots(figsize=(12, 10))
    norm = cm / np.maximum(cm.sum(axis=1, keepdims=True), 1)
    ax.imshow(norm, cmap="Blues")
    ax.set_xticks(range(len(labels)), labels, rotation=90, fontsize=7)
    ax.set_yticks(range(len(labels)), labels, fontsize=7)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title("Role classifier - confusion matrix (validation: unseen styles)")
    fig.tight_layout()
    fig.savefig(ARTIFACTS_DIR / "confusion_matrix.png", dpi=120)
    plt.close(fig)


# --------------------------------------------------------------------------- #
# c) Match regressor
# --------------------------------------------------------------------------- #
def pair_features(pairs: pd.DataFrame, df: pd.DataFrame, probs: np.ndarray, sims: np.ndarray,
                  role_ids: list[str]) -> pd.DataFrame:
    """Build the regressor feature table for (resume, role) pairs."""
    roles = load_roles()
    pos = {rid: i for i, rid in enumerate(df["resume_id"])}
    ridx = {r: i for i, r in enumerate(role_ids)}
    rows = []
    for rid, role_id in zip(pairs["resume_id"], pairs["role_id"]):
        i, j = pos[rid], ridx[role_id]
        f = rule_features(df["parsed_skills"].iat[i], df["parsed_years"].iat[i], roles[role_id])
        f["semantic_similarity"] = float(sims[i, j])
        f["classifier_prob"] = float(probs[i, j])
        rows.append(f)
    return pd.DataFrame(rows)[MATCH_FEATURES]


def regressors() -> dict[str, object]:
    return {
        # monotonic: adding a skill / more similarity can never lower the score
        "HistGradientBoosting (monotonic)": HistGradientBoostingRegressor(
            max_iter=400, learning_rate=0.06, max_leaf_nodes=31, l2_regularization=1.0,
            monotonic_cst=[1] * len(MATCH_FEATURES), random_state=RANDOM_SEED),
        "Ridge": Ridge(alpha=1.0),
    }


def reorder(p: np.ndarray, classes: list[str], role_ids: list[str]) -> np.ndarray:
    idx = [classes.index(r) for r in role_ids]
    return p[:, idx]


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true", help="skip the RandomForest comparison")
    ap.add_argument("--embeddings", default=None, help="auto | sentence-transformers | tfidf")
    args = ap.parse_args()
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    t_start = time.time()

    df, pairs = load_and_parse()
    n_tr, n_va = int((~df.is_val).sum()), int(df.is_val.sum())
    log(f"Train resumes (styles 0-3): {n_tr} | validation resumes (unseen styles 4-5): {n_va}")

    # ---- a) classifier ---------------------------------------------------- #
    log("Training role classifiers...")
    best_name, best_pipe, clf_report = train_classifier(df, args.fast)
    role_ids = list(load_roles())

    # ---- b) embeddings ----------------------------------------------------- #
    log("Fitting TF-IDF fallback embedder and computing semantic similarities...")
    corpus = [role_document(r) for r in load_roles().values()] + df["profile"].tolist()
    tfidf_emb = TfidfEmbedder().fit(corpus)
    tfidf_emb.save()
    embedder = load_embedder(args.embeddings, fallback_corpus=corpus)
    log(f"Embedding backend: {embedder.backend}")
    _, role_matrix = build_role_matrix(embedder)
    sims = np.clip(embedder.encode(df["profile"].tolist()) @ role_matrix.T, 0, 1)
    true_idx = np.array([role_ids.index(r) for r in df["role_id"]])
    sim_top1 = float(np.mean(sims.argmax(axis=1) == true_idx))
    log(f"Semantic similarity alone: top-1 role accuracy = {sim_top1:.3f}")

    # ---- classifier probabilities for the regressor (no leakage) ------------ #
    log("Computing out-of-fold classifier probabilities...")
    tr_mask = (~df.is_val).values
    skf = StratifiedKFold(5, shuffle=True, random_state=RANDOM_SEED)
    X_all = clf_frame(df)
    probs = np.zeros((len(df), len(role_ids)))
    oof_tr = cross_val_predict(clone(best_pipe), X_all[tr_mask], df["role_id"][tr_mask], cv=skf, method="predict_proba")
    classes = sorted(df["role_id"].unique())
    probs[tr_mask] = reorder(oof_tr, classes, role_ids)
    probs[~tr_mask] = reorder(best_pipe.predict_proba(X_all[~tr_mask]), list(best_pipe.classes_), role_ids)

    # ---- c) regressor ------------------------------------------------------- #
    log("Training match-score regressors...")
    pairs = pairs.merge(df[["resume_id", "is_val"]], on="resume_id")
    Xp = pair_features(pairs, df, probs, sims, role_ids)
    yp = pairs["match_score"].values
    vm = pairs["is_val"].values
    reg_results: dict[str, dict] = {}
    fitted_regs = {}
    for name, reg in regressors().items():
        reg.fit(Xp.to_numpy()[~vm], yp[~vm])
        pred = np.clip(reg.predict(Xp.to_numpy()[vm]), 0, 100)
        reg_results[name] = {
            "MAE": round(mean_absolute_error(yp[vm], pred), 3),
            "RMSE": round(float(np.sqrt(mean_squared_error(yp[vm], pred))), 3),
            "R2": round(r2_score(yp[vm], pred), 4),
        }
        fitted_regs[name] = reg
        log(f"  {name:<34} MAE={reg_results[name]['MAE']:.2f}  RMSE={reg_results[name]['RMSE']:.2f}"
            f"  R2={reg_results[name]['R2']:.3f}")
    best_reg_name = min(reg_results, key=lambda k: reg_results[k]["MAE"])
    log(f"Best regressor: {best_reg_name}")

    # ---- ranking quality: is the true role in the top-k? -------------------- #
    va = df[df.is_val].reset_index(drop=True)
    va_idx = np.where(df.is_val.values)[0]
    roles = load_roles()
    reg = fitted_regs[best_reg_name]
    topk = {1: 0, 3: 0, 5: 0}
    for k_row, i in enumerate(va_idx):
        rows = []
        for j, rid in enumerate(role_ids):
            f = rule_features(df["parsed_skills"].iat[i], df["parsed_years"].iat[i], roles[rid])
            f["semantic_similarity"] = float(sims[i, j])
            f["classifier_prob"] = float(probs[i, j])
            rows.append([f[c] for c in MATCH_FEATURES])
        scores = reg.predict(np.array(rows))
        order = np.argsort(-scores)
        rank = int(np.where(order == true_idx[i])[0][0])
        for k in topk:
            topk[k] += rank < k
    topk_acc = {f"top{k}": round(v / len(va), 4) for k, v in topk.items()}
    log(f"Recommendation ranking on unseen styles: {topk_acc}")

    # ---- re-fit on ALL data and save --------------------------------------- #
    log("Re-fitting chosen models on all data...")
    final_clf = clone(best_pipe).fit(X_all, df["role_id"])
    oof_all = cross_val_predict(clone(best_pipe), X_all, df["role_id"], cv=skf, method="predict_proba")
    probs_all = reorder(oof_all, classes, role_ids)
    X_all_pairs = pair_features(pairs, df, probs_all, sims, role_ids)
    final_reg = clone(regressors()[best_reg_name]).fit(X_all_pairs.to_numpy(), yp)
    joblib.dump(final_clf, ARTIFACTS_DIR / "role_classifier.joblib", compress=3)
    joblib.dump(final_reg, ARTIFACTS_DIR / "match_regressor.joblib", compress=3)

    metadata = {
        "trained_at": datetime.now().isoformat(timespec="seconds"),
        "python": platform.python_version(),
        "sklearn": sklearn.__version__,
        "n_resumes": len(df),
        "n_pairs": int(len(pairs)),
        "n_train_resumes": n_tr,
        "n_val_resumes": n_va,
        "validation": "train on synthetic resume styles 0-3, validate on unseen styles 4-5",
        "embedding_backend": embedder.backend,
        "classifier": {"chosen": best_name, **clf_report},
        "semantic_similarity_top1": round(sim_top1, 4),
        "regressor": {"chosen": best_reg_name, "comparison": reg_results, "features": MATCH_FEATURES},
        "ranking": topk_acc,
        "train_minutes": round((time.time() - t_start) / 60, 2),
    }
    (ARTIFACTS_DIR / "metadata.json").write_text(json.dumps(metadata, indent=2))
    log(f"Saved models + metadata to {ARTIFACTS_DIR}")
    print(json.dumps({k: metadata[k] for k in ("classifier", "regressor", "ranking")}, indent=2)[:3000])


if __name__ == "__main__":
    main()
