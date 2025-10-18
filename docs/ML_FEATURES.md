# Machine Learning Features

This document describes the ML-enhanced prediction system in BlueBreaks, which combines physics-based scoring with data-driven machine learning to improve surf spot recommendations.

## Overview

The ML system uses **Positive-Unlabeled (PU) Learning** to train a model from automatically-generated weak labels, then blends the ML predictions with physics scores for robust final rankings.

### Architecture

```
┌─────────────────┐
│  Buoy Data      │
│  (NDBC/NOAA)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────────┐
│ Spatiotemporal  │────▶│ Scanner          │
│ Interpolation   │     │ (Physics Scoring)│
│ (IDW)           │     └────────┬─────────┘
└─────────────────┘              │
                                 ▼
                        ┌──────────────────┐
                        │ Weak Label       │
                        │ Generator        │
                        └────────┬─────────┘
                                 │
                                 ▼
                        ┌──────────────────┐
                        │ Feature          │
                        │ Extractor        │
                        └────────┬─────────┘
                                 │
                                 ▼
                        ┌──────────────────┐
                        │ PU Learning      │
                        │ (LightGBM)       │
                        └────────┬─────────┘
                                 │
                                 ▼
                        ┌──────────────────┐
                        │ Blended Scorer   │
                        │ α*P + (1-α)*ML   │
                        └──────────────────┘
```

## Components

### 1. Buoy Data Loader (`buoy_loader.py`)

Fetches and caches real-time buoy observations from NDBC/NOAA.

**Key Features:**
- Automatic station discovery for regions
- Parses spectral wave data (Hs, Tp, Dp)
- Parses standard meteorological data (wind)
- Local caching to reduce API calls
- Mock data generator for development

**Usage:**
```python
from bluebreaks.core.data.buoy_loader import BuoyDataLoader

loader = BuoyDataLoader(cache_dir="data/buoy_cache")
loader.load_stations(bbox=(-116, 22, -109, 32))

# Get recent observations
observations = loader.get_observations(
    bbox=(-116, 22, -109, 32),
    start_time=datetime.now() - timedelta(days=2)
)
```

**Supported Regions:**
- Baja California (8 stations)
- Southern California
- Northern California
- Hawaii

### 2. Spatiotemporal Interpolation (`interpolation.py`)

Interpolates sparse buoy observations to arbitrary locations and times.

**Algorithm:** Inverse Distance Weighting (IDW)
- **Spatial weighting:** `w = 1 / d^p` (p=2 by default)
- **Temporal weighting:** `w = exp(-Δt / τ)` (exponential decay)
- **Combined weight:** `w_total = w_spatial * w_temporal`

**Special Handling:**
- Circular interpolation for wind/wave directions
- Fallback to GRIB data when buoys unavailable
- Configurable max distance and time windows

**Usage:**
```python
from bluebreaks.core.predict.interpolation import IDWInterpolator

interp = IDWInterpolator(
    power=2.0,
    max_distance_km=500.0,
    max_time_hours=6.0
)

result = interp.interpolate_point(
    target_lat=25.5,
    target_lon=-111.0,
    target_time=datetime.now(),
    observations=buoy_df
)

print(f"Hs: {result['hs']:.1f}m from {result['n_stations']} stations")
```

### 3. Weak Label Generator (`labels.py`)

Generates training labels using physics-based heuristics, avoiding the need for manually-labeled data.

**Labeling Criteria:**
A candidate is labeled **positive** (surfable) if it meets thresholds for:
1. Wave height (1-6m)
2. Period (≥10s)
3. Exposure (≥0.3)
4. Wind compatibility (offshore or light onshore)
5. Tide window (mid-high for beaches)
6. Overall physics score (≥4.0)

**Confidence Scoring:**
- Confidence = geometric mean of condition scores
- Threshold: 0.7 for positive label
- Lower confidence samples get downweighted in training

**Usage:**
```python
from bluebreaks.core.predict.labels import WeakLabelGenerator

generator = WeakLabelGenerator(
    min_hs=1.0,
    min_tp=10.0,
    label_confidence_threshold=0.7
)

labels_df = generator.generate_labels_batch(candidates)
print(f"Generated {len(labels_df)} labels:")
print(labels_df['label'].value_counts())
```

### 4. Feature Extractor (`labels.py`)

Converts raw candidate data into ML-ready feature vectors.

**Feature Categories:**

**Wave Features (6):**
- `hs`, `tp`: Raw wave parameters
- `wave_steepness`: Hs / Tp²
- `wave_energy`: Hs² * Tp (proxy for wave energy)
- `wave_angle`: Incident angle to shore
- `refraction_angle`: Deep to nearshore direction change

**Wind Features (4):**
- `wind_speed`, `wind_angle`
- `is_offshore`, `is_onshore`: Binary indicators

**Geometric Features (5):**
- `curvature`, `is_point`: Break type indicators
- `depth`, `slope`, `depth_slope_ratio`

**Tide Features (1):**
- `tide_height`: Tidal elevation

**Quality Indicators (3):**
- `remoteness`: Distance from roads/marinas
- `lee_shore_risk`: Anchorage safety (binary)
- `physics_score`, `exposure`: Physics components

**Total:** 20+ features

**Usage:**
```python
from bluebreaks.core.predict.labels import FeatureExtractor

extractor = FeatureExtractor()
features_df = extractor.extract_features_batch(candidates)

print(features_df.columns)
# ['hs', 'tp', 'wave_steepness', 'wave_energy', ...]
```

### 5. PU Learning Model (`model.py`)

Trains a gradient boosting model to predict surf quality from features.

**Algorithm:** LightGBM with class weighting
- Positive samples (label=1) get higher weight
- Unlabeled samples (label=0) treated as potential negatives
- Early stopping based on validation AUC

**Hyperparameters:**
```python
n_estimators = 200
max_depth = 6
learning_rate = 0.05
pos_weight = 2.0  # Upweight positive samples
```

**Training:**
```python
from bluebreaks.core.predict.model import PUSurfPredictor

model = PUSurfPredictor(
    n_estimators=200,
    max_depth=6,
    learning_rate=0.05,
    pos_weight=2.0
)

history = model.train(
    X_train=features_train,
    y_train=labels_train,
    confidence=confidence_train,
    X_val=features_val,
    y_val=labels_val
)

print(f"Best iteration: {history['best_iteration']}")
print(f"Best AUC: {history['best_score']['valid']['auc']:.3f}")
```

**Prediction:**
```python
ml_prob = model.predict(features_test)  # Returns probability (0-1)
ml_score = ml_prob * 10.0  # Scale to 0-10 range
```

### 6. Blended Predictor (`model.py`)

Combines physics and ML scores for robust final predictions.

**Formula:**
```
final_score = α * physics_score + (1-α) * ml_score
```

Where:
- `α` = blend weight (default 0.6 = 60% physics, 40% ML)
- `physics_score` = 0-10 score from wave physics
- `ml_score` = 0-10 score from ML model

**Rationale:**
- Physics ensures domain knowledge is respected
- ML captures patterns not modeled by physics
- Blend weight tunable based on model confidence

**Usage:**
```python
from bluebreaks.core.predict.model import BlendedPredictor

blender = BlendedPredictor(pu_model=trained_model, alpha=0.6)

result = blender.predict(
    physics_score=6.5,
    features=feature_dict
)

print(f"Final: {result['final_score']:.1f}")
print(f"  Physics: {result['physics_score']:.1f}")
print(f"  ML: {result['ml_score']:.1f}")
print(f"  ML Prob: {result['ml_prob']:.2f}")
```

### 7. Evaluation Tools (`evaluation.py`)

Tools for model evaluation and temporal analysis.

**Temporal Smoothing:**
Reduces hour-to-hour score jitter using rolling windows.

```python
from bluebreaks.core.predict.evaluation import temporal_smoothing

smoothed_scores = temporal_smoothing(
    times=forecast_times,
    scores=raw_scores,
    window_hours=3,
    method="median"  # or "mean", "ewm"
)
```

**Ranking Metrics:**
- **Precision@K:** Fraction of top-K that are actually positive
- **Hit Rate@K:** Whether at least one positive is in top-K

```python
from bluebreaks.core.predict.evaluation import precision_at_k, hit_rate_at_k

prec = precision_at_k(scores, labels, k=10)
hit = hit_rate_at_k(scores, labels, k=10)

print(f"Precision@10: {prec:.3f}")
print(f"Hit@10: {hit}")
```

**Prediction Comparison:**
Compare physics vs ML vs blended scores.

```python
from bluebreaks.core.predict.evaluation import PredictionComparison

comp = PredictionComparison()

for candidate in candidates:
    comp.add_prediction(
        candidate_id=candidate['id'],
        physics_score=candidate['physics'],
        ml_score=candidate['ml'],
        final_score=candidate['final'],
        true_label=candidate.get('label')
    )

stats = comp.get_statistics()
print(f"ML adjustment: {stats['ml_delta_mean']:.2f} ± {stats['ml_delta_std']:.2f}")
print(f"Physics-ML correlation: {stats['correlation_physics_ml']:.3f}")
```

## API Endpoints

### `/predict` - ML-Enhanced Predictions

Enhanced version of `/scan` with optional ML scoring.

**Parameters:**
- `bbox`: Bounding box (required)
- `time`: ISO timestamp (optional)
- `min_score`: Minimum score threshold
- `spacing`: Point spacing in meters
- `alpha`: Physics blend weight (0-1, default 0.6)
- `model_path`: Path to trained model file (optional)

**Response:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {"type": "Point", "coordinates": [-111.0, 25.0]},
      "properties": {
        "id": "cpt_12345",
        "physics_score": 6.5,
        "ml_score": 7.2,
        "ml_prob": 0.72,
        "final_score": 6.78,
        "blend_alpha": 0.6,
        ...
      }
    }
  ],
  "metadata": {
    "model_used": true,
    "blend_alpha": 0.6,
    ...
  }
}
```

**Examples:**
```bash
# Physics only (no model)
curl "http://localhost:8000/predict?bbox=-116,22,-109,28&min_score=5.0"

# With ML model
curl "http://localhost:8000/predict?bbox=-116,22,-109,28&min_score=5.0&model_path=models/surf_model.txt&alpha=0.6"

# More physics-heavy blend
curl "http://localhost:8000/predict?bbox=-116,22,-109,28&alpha=0.8"
```

## Training a Model

### Step 1: Collect Training Data

Use the training script to scan multiple regions:

```bash
python scripts/train_model.py \
  --regions baja,socal,norcal \
  --spacing 500 \
  --time-samples 5 \
  --output models/surf_model.txt
```

This will:
1. Scan each region at 5 different times (spread over 5 days)
2. Generate ~500-2000 candidates per region
3. Create weak labels using physics heuristics
4. Extract features
5. Train LightGBM model with 80/10/10 train/val/test split
6. Evaluate on test set
7. Save trained model

### Step 2: Evaluate Model

The training script outputs:
- Binary classification metrics (precision, recall, F1, AUC)
- Ranking metrics (Precision@10, Hit@10)
- Feature importance
- Comparison report (physics vs ML vs blended)

Example output:
```
==============================================================
MODEL EVALUATION
==============================================================

Binary Classification Metrics:
  Precision: 0.782
  Recall:    0.691
  F1:        0.734
  AUC:       0.856

Ranking Metrics (Top-10):
  Physics - Precision@10: 0.700, Hit@10: 1.0
  ML      - Precision@10: 0.800, Hit@10: 1.0
  Blended - Precision@10: 0.850, Hit@10: 1.0

Top 10 features:
  physics_score       : 1245.3
  wave_energy         : 892.1
  exposure            : 654.8
  wave_steepness      : 421.5
  ...
```

### Step 3: Use Trained Model

```bash
# Via API
curl "http://localhost:8000/predict?bbox=-116,22,-109,28&model_path=models/surf_model.txt"

# Via Python
from bluebreaks.core.predict.model import PUSurfPredictor, BlendedPredictor

model = PUSurfPredictor()
model.load(Path("models/surf_model.txt"))

blender = BlendedPredictor(pu_model=model, alpha=0.6)
result = blender.predict(physics_score=6.5, features=features)
```

## Best Practices

### 1. Data Collection
- Scan multiple regions for diversity
- Use multiple time samples (different swell/wind conditions)
- Aim for 1000+ candidates minimum for training

### 2. Weak Labeling
- Tune thresholds based on your criteria for "surfable"
- Higher `label_confidence_threshold` = more conservative labels
- Monitor positive/unlabeled ratio (aim for 20-40% positive)

### 3. Model Training
- Use validation set for early stopping
- Monitor feature importance for insights
- Check correlation between physics and ML (should be 0.6-0.8)

### 4. Blend Weight (α)
- **α = 1.0:** Physics only (no ML)
- **α = 0.8:** Mostly physics, ML fine-tunes
- **α = 0.6:** Balanced (default)
- **α = 0.4:** Mostly ML
- **α = 0.0:** ML only (not recommended)

Start with α=0.6 and adjust based on validation performance.

### 5. Temporal Smoothing
- Apply to timeseries forecasts to reduce jitter
- Use 3-hour median smoothing for most cases
- Helps identify stable surf windows

## Troubleshooting

### Model predicts all negatives
- Increase `pos_weight` (try 3.0 or 4.0)
- Lower `label_confidence_threshold` (try 0.6)
- Check positive/unlabeled ratio in training data

### ML scores don't match physics
- Normal! ML learns residual patterns
- Check feature importance for insights
- If correlation < 0.5, may need more/better features

### Poor ranking performance
- Collect more diverse training data
- Tune weak label thresholds
- Try different blend weights (α)

### Model overfits
- Reduce `max_depth` (try 4 or 5)
- Increase `min_child_samples` (try 50)
- Add more data or use stronger regularization

## References

- **PU Learning:** Elkan & Noto (2008), "Learning classifiers from only positive and unlabeled data"
- **LightGBM:** https://lightgbm.readthedocs.io/
- **IDW Interpolation:** Shepard (1968), "A two-dimensional interpolation function for irregularly-spaced data"
- **NDBC Buoy Data:** https://www.ndbc.noaa.gov/

## See Also

- [API Documentation](API.md)
- [Physics Scoring](PHYSICS_SCORING.md)
- [Data Sources](DATA_SOURCES.md)
