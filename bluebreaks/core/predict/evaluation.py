"""
Evaluation and temporal smoothing for surf predictions

Provides tools for:
- Temporal smoothing (rolling median) to reduce score flicker
- Model evaluation metrics (AUC, precision@K, hit rate)
- Visualization of predictions vs physics scores
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


def temporal_smoothing(
    times: List[datetime],
    scores: List[float],
    window_hours: int = 3,
    method: str = "median"
) -> List[float]:
    """
    Apply temporal smoothing to score timeseries

    Reduces hour-to-hour score jitter using a rolling window.

    Args:
        times: List of datetimes
        scores: List of scores
        window_hours: Smoothing window size (hours)
        method: "median", "mean", or "ewm" (exponential weighted moving average)

    Returns:
        Smoothed scores
    """
    if len(times) != len(scores):
        raise ValueError("times and scores must have same length")

    df = pd.DataFrame({"time": times, "score": scores})
    df = df.sort_values("time")

    if method == "median":
        smoothed = df["score"].rolling(window=window_hours, center=True, min_periods=1).median()
    elif method == "mean":
        smoothed = df["score"].rolling(window=window_hours, center=True, min_periods=1).mean()
    elif method == "ewm":
        # Exponential weighted moving average with span = window_hours
        smoothed = df["score"].ewm(span=window_hours, min_periods=1).mean()
    else:
        raise ValueError(f"Unknown smoothing method: {method}")

    return smoothed.tolist()


def calculate_score_stability(
    times: List[datetime],
    scores: List[float]
) -> Dict[str, float]:
    """
    Calculate temporal stability metrics for scores

    Args:
        times: List of datetimes
        scores: List of scores

    Returns:
        Dictionary with stability metrics
    """
    if len(scores) < 2:
        return {"variance": 0.0, "max_change": 0.0, "avg_change": 0.0}

    scores_arr = np.array(scores)

    # Hour-to-hour changes
    diffs = np.diff(scores_arr)

    return {
        "variance": float(np.var(scores_arr)),
        "std_dev": float(np.std(scores_arr)),
        "max_change": float(np.max(np.abs(diffs))),
        "avg_change": float(np.mean(np.abs(diffs))),
        "pct_jitter": float(np.mean(np.abs(diffs) / (scores_arr[:-1] + 1e-6)) * 100)  # % change
    }


def evaluate_predictions(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_score: Optional[np.ndarray] = None
) -> Dict[str, float]:
    """
    Evaluate binary classification predictions

    Args:
        y_true: True labels (0/1)
        y_pred: Predicted labels (0/1)
        y_score: Optional predicted probabilities for AUC

    Returns:
        Dictionary with metrics
    """
    from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score

    metrics = {
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "accuracy": float((y_true == y_pred).mean())
    }

    if y_score is not None:
        try:
            metrics["auc"] = float(roc_auc_score(y_true, y_score))
        except ValueError:
            # Handle case where only one class is present
            metrics["auc"] = np.nan

    return metrics


def precision_at_k(
    scores: List[float],
    labels: List[int],
    k: int = 10
) -> float:
    """
    Calculate precision@K (how many of top-K scored items are actually positive)

    Args:
        scores: Prediction scores
        labels: True labels (1 = positive, 0 = negative)
        k: Number of top items to consider

    Returns:
        Precision@K (0-1)
    """
    if len(scores) != len(labels):
        raise ValueError("scores and labels must have same length")

    # Sort by score (descending)
    sorted_indices = np.argsort(scores)[::-1]

    # Get top-K labels
    top_k_labels = np.array(labels)[sorted_indices[:k]]

    # Precision = fraction of top-K that are positive
    return float(top_k_labels.sum() / k)


def hit_rate_at_k(
    scores: List[float],
    labels: List[int],
    k: int = 10
) -> float:
    """
    Calculate hit rate@K (whether at least one positive is in top-K)

    Args:
        scores: Prediction scores
        labels: True labels (1 = positive, 0 = negative)
        k: Number of top items to consider

    Returns:
        Hit rate (0 or 1)
    """
    if len(scores) != len(labels):
        raise ValueError("scores and labels must have same length")

    # Sort by score (descending)
    sorted_indices = np.argsort(scores)[::-1]

    # Get top-K labels
    top_k_labels = np.array(labels)[sorted_indices[:k]]

    # Hit if any positive in top-K
    return float((top_k_labels > 0).any())


class PredictionComparison:
    """
    Compare physics vs ML vs blended predictions

    Useful for evaluating ML contribution and choosing optimal blend weight (alpha).
    """

    def __init__(self):
        self.comparisons: List[Dict] = []

    def add_prediction(
        self,
        candidate_id: str,
        physics_score: float,
        ml_score: float,
        final_score: float,
        true_label: Optional[int] = None
    ):
        """
        Add a prediction for comparison

        Args:
            candidate_id: Unique ID for candidate
            physics_score: Physics-based score (0-10)
            ml_score: ML predicted score (0-10)
            final_score: Blended final score (0-10)
            true_label: Optional ground truth label (1 = surfable, 0 = not)
        """
        self.comparisons.append({
            "id": candidate_id,
            "physics_score": physics_score,
            "ml_score": ml_score,
            "final_score": final_score,
            "true_label": true_label,
            "ml_delta": ml_score - physics_score,  # How much ML adjusts physics
            "final_delta": final_score - physics_score  # Net adjustment after blending
        })

    def get_statistics(self) -> Dict:
        """
        Get comparison statistics

        Returns:
            Dictionary with statistical summaries
        """
        if not self.comparisons:
            return {}

        df = pd.DataFrame(self.comparisons)

        stats = {
            "n_predictions": len(df),
            "physics_mean": float(df["physics_score"].mean()),
            "ml_mean": float(df["ml_score"].mean()),
            "final_mean": float(df["final_score"].mean()),
            "ml_delta_mean": float(df["ml_delta"].mean()),
            "ml_delta_std": float(df["ml_delta"].std()),
            "correlation_physics_ml": float(df[["physics_score", "ml_score"]].corr().iloc[0, 1])
        }

        # If we have true labels, compute ranking metrics
        if df["true_label"].notna().any():
            valid = df[df["true_label"].notna()]

            for score_type in ["physics_score", "ml_score", "final_score"]:
                scores = valid[score_type].values
                labels = valid["true_label"].values

                stats[f"{score_type}_precision@10"] = precision_at_k(scores, labels, k=10)
                stats[f"{score_type}_hit@10"] = hit_rate_at_k(scores, labels, k=10)

        return stats

    def export_for_plotting(self) -> pd.DataFrame:
        """
        Export data for visualization

        Returns:
            DataFrame ready for plotting
        """
        return pd.DataFrame(self.comparisons)


def create_evaluation_report(
    physics_scores: List[float],
    ml_scores: List[float],
    final_scores: List[float],
    true_labels: Optional[List[int]] = None
) -> str:
    """
    Create a text evaluation report

    Args:
        physics_scores: Physics-based scores
        ml_scores: ML predicted scores
        final_scores: Blended final scores
        true_labels: Optional ground truth labels

    Returns:
        Formatted report string
    """
    report = []
    report.append("=" * 60)
    report.append("SURF PREDICTION EVALUATION REPORT")
    report.append("=" * 60)
    report.append("")

    # Score statistics
    report.append("Score Statistics:")
    report.append(f"  Physics - Mean: {np.mean(physics_scores):.2f}, Std: {np.std(physics_scores):.2f}")
    report.append(f"  ML      - Mean: {np.mean(ml_scores):.2f}, Std: {np.std(ml_scores):.2f}")
    report.append(f"  Final   - Mean: {np.mean(final_scores):.2f}, Std: {np.std(final_scores):.2f}")
    report.append("")

    # ML adjustments
    ml_delta = np.array(ml_scores) - np.array(physics_scores)
    report.append("ML Adjustments:")
    report.append(f"  Mean delta: {np.mean(ml_delta):.2f}")
    report.append(f"  Positive adjustments: {(ml_delta > 0).sum()} ({(ml_delta > 0).mean() * 100:.1f}%)")
    report.append(f"  Negative adjustments: {(ml_delta < 0).sum()} ({(ml_delta < 0).mean() * 100:.1f}%)")
    report.append("")

    # Correlation
    corr = np.corrcoef(physics_scores, ml_scores)[0, 1]
    report.append(f"Physics-ML Correlation: {corr:.3f}")
    report.append("")

    # If we have labels, evaluate ranking
    if true_labels is not None:
        report.append("Ranking Performance (Top-10):")

        for name, scores in [("Physics", physics_scores), ("ML", ml_scores), ("Final", final_scores)]:
            prec = precision_at_k(scores, true_labels, k=10)
            hit = hit_rate_at_k(scores, true_labels, k=10)
            report.append(f"  {name:8s} - Precision@10: {prec:.3f}, Hit@10: {hit:.1f}")

        report.append("")

    report.append("=" * 60)

    return "\n".join(report)
