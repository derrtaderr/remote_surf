"""
PU (Positive-Unlabeled) learning model for surf prediction

Uses LightGBM to learn from weak labels and physics-based features
to predict probability of surfable conditions.

PU Learning approach:
- Positive labels (label=1): High-confidence surfable conditions based on physics heuristics
- Unlabeled (label=0): May or may not be surfable (contains hidden positives)

We treat unlabeled as negative with sample weighting to handle class imbalance.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import logging
import joblib

try:
    import lightgbm as lgb
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False
    logging.warning("LightGBM not installed. Install with: pip install lightgbm")

logger = logging.getLogger(__name__)


class PUSurfPredictor:
    """
    Positive-Unlabeled learning model for surf prediction

    Uses gradient boosting to learn patterns from weak labels,
    combining with physics score for final prediction.
    """

    def __init__(
        self,
        n_estimators: int = 100,
        max_depth: int = 6,
        learning_rate: float = 0.05,
        min_child_samples: int = 20,
        subsample: float = 0.8,
        colsample_bytree: float = 0.8,
        pos_weight: float = 2.0,  # Weight for positive class
        random_state: int = 42
    ):
        """
        Initialize PU predictor

        Args:
            n_estimators: Number of boosting rounds
            max_depth: Maximum tree depth
            learning_rate: Learning rate
            min_child_samples: Minimum samples per leaf
            subsample: Row sampling rate
            colsample_bytree: Column sampling rate
            pos_weight: Weight for positive samples (to handle imbalance)
            random_state: Random seed
        """
        if not HAS_LIGHTGBM:
            raise ImportError("LightGBM is required but not installed")

        self.params = {
            'objective': 'binary',
            'metric': 'auc',
            'boosting_type': 'gbdt',
            'num_leaves': 2 ** max_depth,
            'max_depth': max_depth,
            'learning_rate': learning_rate,
            'n_estimators': n_estimators,
            'min_child_samples': min_child_samples,
            'subsample': subsample,
            'subsample_freq': 1,
            'colsample_bytree': colsample_bytree,
            'random_state': random_state,
            'verbose': -1
        }

        self.pos_weight = pos_weight
        self.model = None
        self.feature_names = None

    def train(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        confidence: Optional[pd.Series] = None,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None
    ) -> Dict:
        """
        Train the PU model

        Args:
            X_train: Training features
            y_train: Training labels (1=positive, 0=unlabeled)
            confidence: Optional confidence weights for each sample
            X_val: Optional validation features
            y_val: Optional validation labels

        Returns:
            Training history dict
        """
        self.feature_names = list(X_train.columns)

        # Create sample weights
        # Positive samples get higher weight to balance with unlabeled
        sample_weights = np.ones(len(y_train))
        sample_weights[y_train == 1] = self.pos_weight

        # Adjust by confidence if provided
        if confidence is not None:
            sample_weights *= confidence.values

        # Create LightGBM datasets
        train_data = lgb.Dataset(
            X_train,
            label=y_train,
            weight=sample_weights,
            feature_name=self.feature_names
        )

        valid_sets = [train_data]
        valid_names = ['train']

        if X_val is not None and y_val is not None:
            val_data = lgb.Dataset(
                X_val,
                label=y_val,
                reference=train_data,
                feature_name=self.feature_names
            )
            valid_sets.append(val_data)
            valid_names.append('valid')

        # Train model
        logger.info(f"Training LightGBM with {len(X_train)} samples ({(y_train == 1).sum()} positive)")

        self.model = lgb.train(
            self.params,
            train_data,
            valid_sets=valid_sets,
            valid_names=valid_names,
            callbacks=[
                lgb.log_evaluation(period=20),
                lgb.early_stopping(stopping_rounds=20, verbose=True)
            ]
        )

        # Get training metrics
        history = {
            'best_iteration': self.model.best_iteration,
            'best_score': self.model.best_score,
            'feature_importance': dict(zip(
                self.feature_names,
                self.model.feature_importance(importance_type='gain')
            ))
        }

        logger.info(f"Training complete. Best iteration: {self.model.best_iteration}")

        return history

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict probability of surfable conditions

        Args:
            X: Feature DataFrame

        Returns:
            Array of probabilities (0-1)
        """
        if self.model is None:
            raise ValueError("Model not trained yet")

        # Ensure features match training
        if list(X.columns) != self.feature_names:
            X = X[self.feature_names]

        return self.model.predict(X, num_iteration=self.model.best_iteration)

    def save(self, path: Path) -> None:
        """Save model to disk"""
        if self.model is None:
            raise ValueError("Model not trained yet")

        model_path = Path(path)
        model_path.parent.mkdir(parents=True, exist_ok=True)

        # Save model
        self.model.save_model(str(model_path))

        # Save metadata
        metadata = {
            'feature_names': self.feature_names,
            'params': self.params,
            'pos_weight': self.pos_weight
        }
        joblib.dump(metadata, str(model_path).replace('.txt', '_metadata.pkl'))

        logger.info(f"Model saved to {model_path}")

    def load(self, path: Path) -> None:
        """Load model from disk"""
        model_path = Path(path)

        if not model_path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")

        # Load model
        self.model = lgb.Booster(model_file=str(model_path))

        # Load metadata
        metadata = joblib.load(str(model_path).replace('.txt', '_metadata.pkl'))
        self.feature_names = metadata['feature_names']
        self.params = metadata['params']
        self.pos_weight = metadata['pos_weight']

        logger.info(f"Model loaded from {model_path}")

    def get_feature_importance(self, top_n: int = 20) -> pd.DataFrame:
        """
        Get feature importance scores

        Args:
            top_n: Number of top features to return

        Returns:
            DataFrame with feature names and importance scores
        """
        if self.model is None:
            raise ValueError("Model not trained yet")

        importance = self.model.feature_importance(importance_type='gain')

        df = pd.DataFrame({
            'feature': self.feature_names,
            'importance': importance
        }).sort_values('importance', ascending=False)

        return df.head(top_n)


class BlendedPredictor:
    """
    Combines physics-based score with ML prediction

    Final score = α * physics_score + (1-α) * ml_score
    """

    def __init__(
        self,
        pu_model: Optional[PUSurfPredictor] = None,
        alpha: float = 0.6,
        ml_scale: float = 10.0
    ):
        """
        Initialize blended predictor

        Args:
            pu_model: Trained PU model (None = physics only)
            alpha: Weight for physics score (0-1), higher = more physics
            ml_scale: Scale factor to convert ML probability to 0-10 range
        """
        self.pu_model = pu_model
        self.alpha = alpha
        self.ml_scale = ml_scale

    def predict(
        self,
        physics_score: float,
        features: Optional[Dict[str, float]] = None
    ) -> Dict[str, float]:
        """
        Predict final score combining physics and ML

        Args:
            physics_score: Physics-based score (0-10)
            features: Optional feature dict for ML prediction

        Returns:
            Dictionary with: {final_score, physics_score, ml_score, ml_prob}
        """
        if self.pu_model is None or features is None:
            # Physics only
            return {
                'final_score': physics_score,
                'physics_score': physics_score,
                'ml_score': np.nan,
                'ml_prob': np.nan,
                'blend_alpha': 1.0
            }

        # Get ML prediction
        feature_df = pd.DataFrame([features])
        ml_prob = self.pu_model.predict(feature_df)[0]
        ml_score = ml_prob * self.ml_scale

        # Blend scores
        final_score = self.alpha * physics_score + (1 - self.alpha) * ml_score

        return {
            'final_score': float(final_score),
            'physics_score': float(physics_score),
            'ml_score': float(ml_score),
            'ml_prob': float(ml_prob),
            'blend_alpha': self.alpha
        }

    def predict_batch(
        self,
        candidates: List[Dict]
    ) -> List[Dict]:
        """
        Predict for batch of candidates

        Args:
            candidates: List of candidate dicts with physics_score and features

        Returns:
            Updated candidates with final_score added
        """
        from bluebreaks.core.predict.labels import FeatureExtractor

        extractor = FeatureExtractor()

        for candidate in candidates:
            physics_score = candidate.get('score', {}).get('total', 0)

            # Extract features
            features = extractor.extract_features(candidate)

            # Predict
            result = self.predict(physics_score, features)

            # Update candidate
            if 'score' not in candidate:
                candidate['score'] = {}

            candidate['score']['final'] = result['final_score']
            candidate['score']['ml_prob'] = result['ml_prob']
            candidate['score']['ml_score'] = result['ml_score']
            candidate['score']['blend_alpha'] = result['blend_alpha']

        return candidates
