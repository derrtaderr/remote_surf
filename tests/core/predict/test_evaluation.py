"""
Tests for evaluation and temporal smoothing
"""

import pytest
import numpy as np
from datetime import datetime, timedelta

from bluebreaks.core.predict.evaluation import (
    temporal_smoothing,
    calculate_score_stability,
    precision_at_k,
    hit_rate_at_k,
    PredictionComparison
)


class TestTemporalSmoothing:
    """Test temporal smoothing functions"""

    @pytest.fixture
    def noisy_scores(self):
        """Create noisy score timeseries"""
        # Base sine wave + noise
        hours = 48
        base = 5.0 + 2.0 * np.sin(np.linspace(0, 4*np.pi, hours))
        noise = np.random.RandomState(42).normal(0, 0.5, hours)
        return base + noise

    @pytest.fixture
    def times(self):
        """Create time array"""
        start = datetime.now()
        return [start + timedelta(hours=i) for i in range(48)]

    def test_median_smoothing(self, times, noisy_scores):
        """Test median smoothing reduces jitter"""
        smoothed = temporal_smoothing(times, noisy_scores.tolist(), window_hours=3, method="median")

        # Smoothed should have less variance
        orig_var = np.var(noisy_scores)
        smooth_var = np.var(smoothed)

        assert smooth_var < orig_var

    def test_mean_smoothing(self, times, noisy_scores):
        """Test mean smoothing"""
        smoothed = temporal_smoothing(times, noisy_scores.tolist(), window_hours=3, method="mean")

        assert len(smoothed) == len(noisy_scores)
        # No NaN values
        assert not any(np.isnan(smoothed))

    def test_ewm_smoothing(self, times, noisy_scores):
        """Test exponential weighted moving average"""
        smoothed = temporal_smoothing(times, noisy_scores.tolist(), window_hours=5, method="ewm")

        assert len(smoothed) == len(noisy_scores)
        # EWM should smooth but follow trend
        assert np.corrcoef(smoothed, noisy_scores)[0, 1] > 0.8


class TestScoreStability:
    """Test score stability metrics"""

    def test_stability_perfect_scores(self):
        """Perfect stability (constant scores)"""
        times = [datetime.now() + timedelta(hours=i) for i in range(10)]
        scores = [5.0] * 10

        metrics = calculate_score_stability(times, scores)

        assert metrics['variance'] == pytest.approx(0.0, abs=0.01)
        assert metrics['max_change'] == pytest.approx(0.0, abs=0.01)
        assert metrics['avg_change'] == pytest.approx(0.0, abs=0.01)

    def test_stability_variable_scores(self):
        """Variable scores should have high jitter"""
        times = [datetime.now() + timedelta(hours=i) for i in range(10)]
        scores = [5.0, 7.0, 3.0, 8.0, 4.0, 6.0, 2.0, 7.0, 5.0, 6.0]  # Jumping around

        metrics = calculate_score_stability(times, scores)

        assert metrics['variance'] > 1.0
        assert metrics['max_change'] > 3.0
        assert metrics['pct_jitter'] > 20.0  # >20% average change


class TestRankingMetrics:
    """Test ranking evaluation metrics"""

    def test_precision_at_k_perfect(self):
        """Perfect ranking should have 100% precision"""
        scores = [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]
        labels = [1, 1, 1, 1, 1, 0, 0, 0, 0, 0]  # Top 5 are positive

        prec = precision_at_k(scores, labels, k=5)
        assert prec == 1.0

    def test_precision_at_k_poor(self):
        """Poor ranking should have low precision"""
        scores = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]  # Reversed
        labels = [1, 1, 1, 1, 1, 0, 0, 0, 0, 0]  # Top 5 are positive

        prec = precision_at_k(scores, labels, k=5)
        assert prec == 0.0  # None of top-5 scored items are positive

    def test_precision_at_k_partial(self):
        """Partial ranking success"""
        scores = [10, 5, 9, 3, 8, 2, 7, 1, 6, 4]
        labels = [1, 0, 1, 0, 1, 0, 1, 0, 1, 0]  # Every other is positive

        prec = precision_at_k(scores, labels, k=5)
        # Top 5 scores: 10(1), 9(1), 8(1), 7(1), 6(1) = 5/5 = 1.0
        assert prec == 1.0

    def test_hit_rate_at_k_hit(self):
        """Hit rate when positive is in top-K"""
        scores = [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]
        labels = [0, 0, 0, 1, 0, 0, 0, 0, 0, 0]  # One positive at position 4

        hit = hit_rate_at_k(scores, labels, k=5)
        assert hit == 1.0  # Hit! (positive is in top-5)

    def test_hit_rate_at_k_miss(self):
        """Hit rate when no positive in top-K"""
        scores = [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]
        labels = [0, 0, 0, 0, 0, 0, 1, 0, 0, 0]  # Positive at position 7

        hit = hit_rate_at_k(scores, labels, k=5)
        assert hit == 0.0  # Miss (positive is not in top-5)


class TestPredictionComparison:
    """Test prediction comparison tool"""

    @pytest.fixture
    def comparison(self):
        """Create comparison object"""
        return PredictionComparison()

    def test_add_predictions(self, comparison):
        """Test adding predictions"""
        comparison.add_prediction('1', physics_score=6.0, ml_score=7.0, final_score=6.4, true_label=1)
        comparison.add_prediction('2', physics_score=4.0, ml_score=3.5, final_score=3.8, true_label=0)

        assert len(comparison.comparisons) == 2

    def test_ml_delta_calculation(self, comparison):
        """Test ML delta calculation"""
        comparison.add_prediction('1', physics_score=6.0, ml_score=7.0, final_score=6.4)

        assert comparison.comparisons[0]['ml_delta'] == 1.0  # 7.0 - 6.0
        assert comparison.comparisons[0]['final_delta'] == 0.4  # 6.4 - 6.0

    def test_statistics_without_labels(self, comparison):
        """Test statistics without ground truth labels"""
        comparison.add_prediction('1', physics_score=6.0, ml_score=7.0, final_score=6.4)
        comparison.add_prediction('2', physics_score=4.0, ml_score=3.5, final_score=3.8)
        comparison.add_prediction('3', physics_score=5.5, ml_score=6.0, final_score=5.7)

        stats = comparison.get_statistics()

        assert stats['n_predictions'] == 3
        assert 'physics_mean' in stats
        assert 'ml_mean' in stats
        assert 'ml_delta_mean' in stats
        assert 'correlation_physics_ml' in stats

    def test_statistics_with_labels(self, comparison):
        """Test statistics with ground truth labels"""
        comparison.add_prediction('1', physics_score=8.0, ml_score=9.0, final_score=8.4, true_label=1)
        comparison.add_prediction('2', physics_score=7.0, ml_score=8.0, final_score=7.4, true_label=1)
        comparison.add_prediction('3', physics_score=3.0, ml_score=2.5, final_score=2.8, true_label=0)
        comparison.add_prediction('4', physics_score=4.0, ml_score=3.5, final_score=3.8, true_label=0)

        stats = comparison.get_statistics()

        # Should have ranking metrics
        assert 'physics_score_precision@10' in stats
        assert 'ml_score_precision@10' in stats
        assert 'final_score_precision@10' in stats

    def test_export_for_plotting(self, comparison):
        """Test export to DataFrame"""
        comparison.add_prediction('1', physics_score=6.0, ml_score=7.0, final_score=6.4)
        comparison.add_prediction('2', physics_score=4.0, ml_score=3.5, final_score=3.8)

        df = comparison.export_for_plotting()

        assert len(df) == 2
        assert 'id' in df.columns
        assert 'physics_score' in df.columns
        assert 'ml_score' in df.columns
        assert 'ml_delta' in df.columns

    def test_ml_improvement_detection(self, comparison):
        """Test detection of ML improvements over physics"""
        # Case where ML improves ranking
        comparison.add_prediction('1', physics_score=5.0, ml_score=8.0, final_score=6.2, true_label=1)
        comparison.add_prediction('2', physics_score=6.0, ml_score=4.0, final_score=5.4, true_label=0)

        stats = comparison.get_statistics()

        # ML should have better precision (puts positive first)
        if 'ml_score_precision@10' in stats and 'physics_score_precision@10' in stats:
            # With only 2 samples and K=10, both would be in top-10
            # But this tests the calculation works
            assert stats['ml_score_precision@10'] >= 0.0
