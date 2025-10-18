#!/usr/bin/env python3
"""
Train surf prediction model

This script:
1. Scans multiple coastline regions to generate training data
2. Generates weak labels based on physics heuristics
3. Extracts features for ML
4. Trains a PU learning model with LightGBM
5. Evaluates the model
6. Saves the trained model

Usage:
    python scripts/train_model.py --regions baja,socal --output models/surf_model.txt

Requirements:
    - GRIB data (optional, will use mock if unavailable)
    - Bathymetry data (optional)
    - Coastline data (optional)
"""

import argparse
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from bluebreaks.core.scanner import CoastlineScanner
from bluebreaks.core.predict.labels import WeakLabelGenerator, FeatureExtractor
from bluebreaks.core.predict.model import PUSurfPredictor
from bluebreaks.core.predict.evaluation import (
    evaluate_predictions,
    precision_at_k,
    hit_rate_at_k,
    create_evaluation_report
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Predefined regions for training
REGIONS = {
    "baja": {
        "name": "Baja California",
        "bbox": (-116.0, 22.0, -109.0, 32.0),
        "description": "Baja peninsula, Mexico"
    },
    "socal": {
        "name": "Southern California",
        "bbox": (-120.5, 32.5, -117.0, 34.5),
        "description": "Southern California coast"
    },
    "norcal": {
        "name": "Northern California",
        "bbox": (-124.5, 36.0, -121.0, 42.0),
        "description": "Northern California coast"
    },
    "hawaii": {
        "name": "Hawaii",
        "bbox": (-160.0, 18.0, -154.0, 22.5),
        "description": "Hawaiian Islands"
    }
}


def generate_training_data(
    regions: List[str],
    spacing_m: float = 500.0,
    num_time_samples: int = 5,
    data_dir: Path = Path("data")
) -> List[Dict]:
    """
    Generate training data by scanning multiple regions and times

    Args:
        regions: List of region names (keys in REGIONS dict)
        spacing_m: Candidate point spacing
        num_time_samples: Number of different forecast times to sample
        data_dir: Data directory path

    Returns:
        List of candidate dictionaries
    """
    all_candidates = []

    # Setup paths
    grib_path = data_dir / "grib"
    bathy_path = data_dir / "bathymetry"
    coastline_path = data_dir / "coastline"

    # Check what data is available
    has_grib = (grib_path / "latest.grb2").exists() if grib_path.exists() else False
    has_bathy = bathy_path.exists() and any(bathy_path.glob("*.nc"))
    has_coastline = coastline_path.exists() and any(coastline_path.glob("*.shp"))

    logger.info(f"Data availability: GRIB={has_grib}, Bathy={has_bathy}, Coastline={has_coastline}")

    for region_name in regions:
        if region_name not in REGIONS:
            logger.warning(f"Unknown region: {region_name}, skipping")
            continue

        region = REGIONS[region_name]
        logger.info(f"Scanning region: {region['name']} - {region['description']}")

        # Sample different times (spread over 5 days)
        base_time = datetime.now()
        time_samples = [base_time + timedelta(hours=i*24) for i in range(num_time_samples)]

        for i, time_sample in enumerate(time_samples):
            logger.info(f"  Time sample {i+1}/{num_time_samples}: {time_sample.isoformat()}")

            try:
                # Initialize scanner
                scanner = CoastlineScanner(
                    grib_path=grib_path / "latest.grb2" if has_grib else None,
                    bathy_path=bathy_path if has_bathy else None,
                    coastline_path=coastline_path if has_coastline else None
                )

                # Scan region
                geojson = scanner.scan(
                    bbox=region["bbox"],
                    time=time_sample,
                    spacing_m=spacing_m,
                    min_score=0.0  # Get all candidates
                )

                scanner.close()

                # Convert GeoJSON to candidate dicts
                for feature in geojson["features"]:
                    props = feature["properties"]
                    candidate = {
                        "id": props["id"],
                        "lat": feature["geometry"]["coordinates"][1],
                        "lon": feature["geometry"]["coordinates"][0],
                        "region": region_name,
                        "time": time_sample.isoformat(),
                        "shore_normal": props["shore_normal"],
                        "curvature": props["curvature"],
                        "depth": props.get("depth_m", 10.0),
                        "slope": props.get("slope", 0.05),
                        "score": {
                            "total": props["physics_score"],
                            "components": props["components"]
                        },
                        "wave": props["swell"],
                        "wind": props["wind"],
                        "tide": props.get("tide", {}),
                        "anchorage": props.get("anchorage", {}),
                        "remoteness": props.get("remoteness", 0)
                    }
                    all_candidates.append(candidate)

                logger.info(f"    Generated {len(geojson['features'])} candidates")

            except Exception as e:
                logger.error(f"Failed to scan {region_name} at {time_sample}: {e}", exc_info=True)
                continue

    logger.info(f"Total candidates generated: {len(all_candidates)}")
    return all_candidates


def prepare_training_data(
    candidates: List[Dict]
) -> Tuple[pd.DataFrame, pd.Series, pd.Series]:
    """
    Prepare features and labels for training

    Args:
        candidates: List of candidate dicts

    Returns:
        Tuple of (features_df, labels, confidences)
    """
    logger.info("Generating weak labels...")

    # Generate labels
    label_gen = WeakLabelGenerator(
        min_hs=1.0,
        max_hs=6.0,
        min_tp=10.0,
        min_exposure=0.3,
        min_physics_score=4.0,
        label_confidence_threshold=0.7
    )

    labels_df = label_gen.generate_labels_batch(candidates)

    logger.info(f"Label distribution: {labels_df['label'].value_counts().to_dict()}")
    logger.info(f"Mean confidence: {labels_df['confidence'].mean():.3f}")

    # Extract features
    logger.info("Extracting features...")
    feature_extractor = FeatureExtractor()
    features_df = feature_extractor.extract_features_batch(candidates)

    # Merge labels and features
    data = features_df.merge(labels_df[['id', 'label', 'confidence']], on='id')

    # Separate features, labels, and confidences
    feature_cols = [col for col in data.columns if col not in ['id', 'lat', 'lon', 'label', 'confidence']]
    X = data[feature_cols]
    y = data['label']
    confidence = data['confidence']

    logger.info(f"Features: {len(feature_cols)} columns")
    logger.info(f"Samples: {len(X)} total, {y.sum()} positive, {(y == 0).sum()} unlabeled")

    return X, y, confidence


def train_model(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    confidence_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series
) -> PUSurfPredictor:
    """
    Train PU learning model

    Args:
        X_train: Training features
        y_train: Training labels
        confidence_train: Training confidences
        X_val: Validation features
        y_val: Validation labels

    Returns:
        Trained model
    """
    logger.info("Training PU model...")

    model = PUSurfPredictor(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.05,
        min_child_samples=20,
        subsample=0.8,
        colsample_bytree=0.8,
        pos_weight=2.0,
        random_state=42
    )

    history = model.train(
        X_train=X_train,
        y_train=y_train,
        confidence=confidence_train,
        X_val=X_val,
        y_val=y_val
    )

    logger.info(f"Training complete. Best iteration: {history['best_iteration']}")
    logger.info(f"Best score: {history['best_score']}")

    # Print feature importance
    logger.info("\nTop 10 features:")
    importance_df = model.get_feature_importance(top_n=10)
    for idx, row in importance_df.iterrows():
        logger.info(f"  {row['feature']:20s}: {row['importance']:.1f}")

    return model


def evaluate_model(
    model: PUSurfPredictor,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    physics_scores: List[float]
) -> None:
    """
    Evaluate trained model

    Args:
        model: Trained model
        X_test: Test features
        y_test: Test labels
        physics_scores: Physics scores for comparison
    """
    logger.info("\n" + "="*60)
    logger.info("MODEL EVALUATION")
    logger.info("="*60)

    # Get ML predictions
    ml_probs = model.predict(X_test)
    ml_scores = ml_probs * 10.0  # Scale to 0-10

    # Convert to binary predictions
    ml_preds = (ml_probs > 0.5).astype(int)

    # Evaluate binary classification
    metrics = evaluate_predictions(y_test.values, ml_preds, ml_probs)

    logger.info("\nBinary Classification Metrics:")
    logger.info(f"  Precision: {metrics['precision']:.3f}")
    logger.info(f"  Recall:    {metrics['recall']:.3f}")
    logger.info(f"  F1:        {metrics['f1']:.3f}")
    logger.info(f"  AUC:       {metrics['auc']:.3f}")

    # Evaluate ranking
    logger.info("\nRanking Metrics (Top-10):")
    physics_prec = precision_at_k(physics_scores, y_test.tolist(), k=10)
    ml_prec = precision_at_k(ml_scores.tolist(), y_test.tolist(), k=10)

    physics_hit = hit_rate_at_k(physics_scores, y_test.tolist(), k=10)
    ml_hit = hit_rate_at_k(ml_scores.tolist(), y_test.tolist(), k=10)

    logger.info(f"  Physics - Precision@10: {physics_prec:.3f}, Hit@10: {physics_hit:.1f}")
    logger.info(f"  ML      - Precision@10: {ml_prec:.3f}, Hit@10: {ml_hit:.1f}")

    # Blended scores (alpha=0.6)
    alpha = 0.6
    blended_scores = alpha * np.array(physics_scores) + (1 - alpha) * ml_scores
    blended_prec = precision_at_k(blended_scores.tolist(), y_test.tolist(), k=10)
    blended_hit = hit_rate_at_k(blended_scores.tolist(), y_test.tolist(), k=10)

    logger.info(f"  Blended - Precision@10: {blended_prec:.3f}, Hit@10: {blended_hit:.1f}")

    # Generate full report
    report = create_evaluation_report(
        physics_scores=physics_scores,
        ml_scores=ml_scores.tolist(),
        final_scores=blended_scores.tolist(),
        true_labels=y_test.tolist()
    )

    logger.info("\n" + report)


def main():
    parser = argparse.ArgumentParser(description="Train surf prediction model")

    parser.add_argument(
        "--regions",
        type=str,
        default="baja,socal",
        help="Comma-separated list of regions to train on (default: baja,socal)"
    )
    parser.add_argument(
        "--spacing",
        type=float,
        default=500.0,
        help="Candidate point spacing in meters (default: 500)"
    )
    parser.add_argument(
        "--time-samples",
        type=int,
        default=5,
        help="Number of time samples per region (default: 5)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="models/surf_model.txt",
        help="Output model file path (default: models/surf_model.txt)"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data",
        help="Data directory path (default: data)"
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.2,
        help="Test set fraction (default: 0.2)"
    )
    parser.add_argument(
        "--val-size",
        type=float,
        default=0.1,
        help="Validation set fraction (default: 0.1)"
    )

    args = parser.parse_args()

    # Parse regions
    regions = [r.strip() for r in args.regions.split(",")]
    logger.info(f"Training on regions: {regions}")

    # Generate training data
    logger.info("="*60)
    logger.info("STEP 1: GENERATE TRAINING DATA")
    logger.info("="*60)

    candidates = generate_training_data(
        regions=regions,
        spacing_m=args.spacing,
        num_time_samples=args.time_samples,
        data_dir=Path(args.data_dir)
    )

    if len(candidates) == 0:
        logger.error("No training data generated. Exiting.")
        return 1

    # Prepare data
    logger.info("\n" + "="*60)
    logger.info("STEP 2: PREPARE FEATURES AND LABELS")
    logger.info("="*60)

    X, y, confidence = prepare_training_data(candidates)

    # Split data
    logger.info(f"\nSplitting data: {100*(1-args.test_size-args.val_size):.0f}% train, {100*args.val_size:.0f}% val, {100*args.test_size:.0f}% test")

    # First split: train+val vs test
    X_temp, X_test, y_temp, y_test, conf_temp, conf_test = train_test_split(
        X, y, confidence, test_size=args.test_size, random_state=42, stratify=y
    )

    # Second split: train vs val
    val_fraction = args.val_size / (1 - args.test_size)
    X_train, X_val, y_train, y_val, conf_train, conf_val = train_test_split(
        X_temp, y_temp, conf_temp, test_size=val_fraction, random_state=42, stratify=y_temp
    )

    logger.info(f"Train: {len(X_train)} samples ({y_train.sum()} positive)")
    logger.info(f"Val:   {len(X_val)} samples ({y_val.sum()} positive)")
    logger.info(f"Test:  {len(X_test)} samples ({y_test.sum()} positive)")

    # Train model
    logger.info("\n" + "="*60)
    logger.info("STEP 3: TRAIN MODEL")
    logger.info("="*60)

    model = train_model(X_train, y_train, conf_train, X_val, y_val)

    # Evaluate
    logger.info("\n" + "="*60)
    logger.info("STEP 4: EVALUATE MODEL")
    logger.info("="*60)

    physics_scores_test = X_test['physics_score'].tolist()
    evaluate_model(model, X_test, y_test, physics_scores_test)

    # Save model
    logger.info("\n" + "="*60)
    logger.info("STEP 5: SAVE MODEL")
    logger.info("="*60)

    output_path = Path(args.output)
    model.save(output_path)

    logger.info(f"\n✓ Model saved to: {output_path}")
    logger.info(f"✓ Training complete!")
    logger.info(f"\nTo use the model, run:")
    logger.info(f"  /predict?bbox=...&model_path={output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
