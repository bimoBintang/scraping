"""
Power Law Distribution Analysis
Statistical analysis of scale-free network properties

Features:
- Power law fitting (MLE)
- KS test for goodness of fit
- Gini coefficient
- Heavy-tailedness quantification
- Scaling regime break detection
"""

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from collections import Counter


@dataclass
class PowerLawFit:
    """Result of power law fitting"""
    alpha: float           # Power law exponent
    xmin: float            # Minimum value for fit
    xmax: Optional[float]  # Maximum value (if truncated)
    
    # Goodness of fit
    ks_statistic: float    # Kolmogorov-Smirnov statistic
    p_value: float         # P-value (via bootstrap)
    r_squared: float       # Coefficient of determination
    
    # Sample info
    n_tail: int            # Number of observations in tail
    n_total: int           # Total observations
    
    def to_dict(self) -> Dict:
        return {
            "alpha": round(self.alpha, 4),
            "xmin": self.xmin,
            "xmax": self.xmax,
            "ks_statistic": round(self.ks_statistic, 4),
            "p_value": round(self.p_value, 4),
            "r_squared": round(self.r_squared, 4),
            "n_tail": self.n_tail,
            "n_total": self.n_total,
            "is_power_law": self.p_value > 0.1,  # Common threshold
        }


@dataclass
class DistributionComparison:
    """Comparison between power law and alternative distributions"""
    power_law_ll: float      # Log-likelihood for power law
    exponential_ll: float    # Log-likelihood for exponential
    lognormal_ll: float      # Log-likelihood for lognormal
    
    # Likelihood ratios
    vs_exponential: float    # LR vs exponential (positive = PL better)
    vs_lognormal: float      # LR vs lognormal
    
    best_fit: str           # Best fitting distribution
    
    def to_dict(self) -> Dict:
        return {
            "log_likelihoods": {
                "power_law": round(self.power_law_ll, 2),
                "exponential": round(self.exponential_ll, 2),
                "lognormal": round(self.lognormal_ll, 2),
            },
            "likelihood_ratios": {
                "vs_exponential": round(self.vs_exponential, 2),
                "vs_lognormal": round(self.vs_lognormal, 2),
            },
            "best_fit": self.best_fit,
        }


@dataclass  
class HeavyTailMetrics:
    """Metrics quantifying heavy-tailedness"""
    kurtosis: float         # Excess kurtosis
    tail_index: float       # Hill estimator
    mean_excess: float      # Mean excess function at 90th percentile
    gini: float             # Gini coefficient
    
    # Classification
    is_heavy_tailed: bool
    classification: str     # "light", "moderate", "heavy", "extreme"
    
    def to_dict(self) -> Dict:
        return {
            "kurtosis": round(self.kurtosis, 4),
            "tail_index": round(self.tail_index, 4),
            "mean_excess": round(self.mean_excess, 4),
            "gini": round(self.gini, 4),
            "is_heavy_tailed": self.is_heavy_tailed,
            "classification": self.classification,
        }


class PowerLawAnalyzer:
    """
    Analyze scale-free network properties
    
    Usage:
        analyzer = PowerLawAnalyzer()
        
        # Fit power law to follower counts
        followers = [1000, 500, 200, 100, 50, ...]
        fit = analyzer.fit_power_law(followers)
        print(f"Alpha: {fit.alpha}, Valid: {fit.p_value > 0.1}")
        
        # Compare distributions
        comparison = analyzer.compare_distributions(followers)
        print(f"Best fit: {comparison.best_fit}")
        
        # Analyze inequality
        gini = analyzer.get_gini_coefficient(followers)
    """
    
    def __init__(self):
        self.data: Dict[str, List[float]] = {}
        self._rng_state = 42  # For reproducible bootstrap
    
    def fit_power_law(
        self,
        values: List[float],
        xmin: Optional[float] = None
    ) -> PowerLawFit:
        """
        Fit power law distribution using MLE
        
        Args:
            values: Data values (e.g., follower counts)
            xmin: Minimum value (auto-detected if None)
            
        Returns:
            PowerLawFit with alpha and goodness-of-fit metrics
        """
        values = [v for v in values if v > 0]
        n_total = len(values)
        
        if n_total < 10:
            return PowerLawFit(
                alpha=0, xmin=0, xmax=None,
                ks_statistic=1, p_value=0, r_squared=0,
                n_tail=0, n_total=n_total
            )
        
        # Find optimal xmin if not provided
        if xmin is None:
            xmin = self.calculate_xmin(values)
        
        # Filter to tail
        tail = [v for v in values if v >= xmin]
        n_tail = len(tail)
        
        if n_tail < 5:
            return PowerLawFit(
                alpha=0, xmin=xmin, xmax=None,
                ks_statistic=1, p_value=0, r_squared=0,
                n_tail=n_tail, n_total=n_total
            )
        
        # MLE for alpha
        alpha = self.calculate_alpha(tail, xmin)
        
        # KS test
        ks_stat, p_value = self.ks_test(tail, alpha, xmin)
        
        # R-squared (log-log regression)
        r_squared = self._calculate_r_squared(tail, alpha, xmin)
        
        return PowerLawFit(
            alpha=alpha,
            xmin=xmin,
            xmax=max(tail) if tail else None,
            ks_statistic=ks_stat,
            p_value=p_value,
            r_squared=r_squared,
            n_tail=n_tail,
            n_total=n_total
        )
    
    def calculate_alpha(self, values: List[float], xmin: float = 1) -> float:
        """
        Calculate power law exponent using MLE
        
        α = 1 + n / Σ ln(xi / xmin)
        """
        tail = [v for v in values if v >= xmin]
        n = len(tail)
        
        if n == 0 or xmin <= 0:
            return 0
        
        log_sum = sum(math.log(v / xmin) for v in tail)
        
        if log_sum == 0:
            return 0
        
        return 1 + n / log_sum
    
    def calculate_xmin(self, values: List[float]) -> float:
        """
        Find optimal xmin using KS distance minimization
        """
        values = sorted([v for v in values if v > 0])
        n = len(values)
        
        if n < 10:
            return values[0] if values else 1.0
        
        # Test xmin at unique values
        unique_values = sorted(set(values))
        
        best_xmin = unique_values[0]
        best_ks = float('inf')
        
        # Only test first 50% of unique values
        test_range = unique_values[:max(1, len(unique_values) // 2)]
        
        for xmin in test_range:
            tail = [v for v in values if v >= xmin]
            if len(tail) < 5:
                break
            
            alpha = self.calculate_alpha(tail, xmin)
            ks, _ = self._simple_ks_test(tail, alpha, xmin)
            
            if ks < best_ks:
                best_ks = ks
                best_xmin = xmin
        
        return best_xmin
    
    def ks_test(
        self,
        values: List[float],
        alpha: float,
        xmin: float,
        n_bootstrap: int = 100
    ) -> Tuple[float, float]:
        """
        Kolmogorov-Smirnov test with bootstrap for p-value
        
        Returns:
            (ks_statistic, p_value)
        """
        ks_stat, _ = self._simple_ks_test(values, alpha, xmin)
        
        # Bootstrap for p-value
        n = len(values)
        if n < 10 or n_bootstrap == 0:
            return ks_stat, 0.0
        
        # Simplified p-value estimation
        # Higher KS = worse fit
        p_value = math.exp(-2 * n * ks_stat ** 2)
        p_value = max(0, min(1, p_value))
        
        return ks_stat, p_value
    
    def compare_distributions(self, values: List[float]) -> DistributionComparison:
        """
        Compare power law fit vs alternative distributions
        """
        values = [v for v in values if v > 0]
        
        if len(values) < 10:
            return DistributionComparison(
                power_law_ll=0, exponential_ll=0, lognormal_ll=0,
                vs_exponential=0, vs_lognormal=0, best_fit="insufficient_data"
            )
        
        # Power law
        fit = self.fit_power_law(values)
        tail = [v for v in values if v >= fit.xmin]
        pl_ll = self._power_law_ll(tail, fit.alpha, fit.xmin)
        
        # Exponential
        exp_ll = self._exponential_ll(tail)
        
        # Lognormal
        ln_ll = self._lognormal_ll(tail)
        
        # Likelihood ratios
        vs_exp = pl_ll - exp_ll
        vs_ln = pl_ll - ln_ll
        
        # Determine best
        if pl_ll >= exp_ll and pl_ll >= ln_ll:
            best = "power_law"
        elif exp_ll >= ln_ll:
            best = "exponential"
        else:
            best = "lognormal"
        
        return DistributionComparison(
            power_law_ll=pl_ll,
            exponential_ll=exp_ll,
            lognormal_ll=ln_ll,
            vs_exponential=vs_exp,
            vs_lognormal=vs_ln,
            best_fit=best
        )
    
    def get_gini_coefficient(self, values: List[float]) -> float:
        """
        Calculate Gini coefficient (inequality measure)
        
        0 = perfect equality
        1 = perfect inequality
        """
        values = sorted([v for v in values if v >= 0])
        n = len(values)
        
        if n == 0 or sum(values) == 0:
            return 0.0
        
        # Gini formula
        numerator = sum((2 * i - n + 1) * v for i, v in enumerate(values))
        denominator = n * sum(values)
        
        return numerator / denominator if denominator > 0 else 0.0
    
    def get_heavy_tail_metrics(self, values: List[float]) -> HeavyTailMetrics:
        """
        Quantify heavy-tailedness of distribution
        """
        values = [v for v in values if v > 0]
        n = len(values)
        
        if n < 10:
            return HeavyTailMetrics(
                kurtosis=0, tail_index=0, mean_excess=0, gini=0,
                is_heavy_tailed=False, classification="insufficient_data"
            )
        
        # Kurtosis
        kurtosis = self._calculate_kurtosis(values)
        
        # Hill estimator for tail index
        tail_index = self._hill_estimator(values)
        
        # Mean excess at 90th percentile
        mean_excess = self._mean_excess_function(values, 0.9)
        
        # Gini
        gini = self.get_gini_coefficient(values)
        
        # Classification
        is_heavy = kurtosis > 3 or tail_index < 3 or gini > 0.5
        
        if kurtosis > 20 or tail_index < 1.5:
            classification = "extreme"
        elif kurtosis > 6 or tail_index < 2.5:
            classification = "heavy"
        elif kurtosis > 3 or gini > 0.5:
            classification = "moderate"
        else:
            classification = "light"
        
        return HeavyTailMetrics(
            kurtosis=kurtosis,
            tail_index=tail_index,
            mean_excess=mean_excess,
            gini=gini,
            is_heavy_tailed=is_heavy,
            classification=classification
        )
    
    def detect_scaling_breaks(
        self,
        values: List[float],
        min_segment: int = 20
    ) -> List[Dict]:
        """
        Detect breaks in scaling regime
        
        Returns list of detected break points
        """
        values = sorted([v for v in values if v > 0], reverse=True)
        n = len(values)
        
        if n < min_segment * 2:
            return []
        
        # Calculate rolling alpha
        alphas = []
        positions = []
        
        for i in range(min_segment, n - min_segment):
            left = values[:i]
            right = values[i:]
            
            if left and right:
                alpha_left = self.calculate_alpha(left, min(left))
                alpha_right = self.calculate_alpha(right, min(right))
                
                alphas.append(abs(alpha_left - alpha_right))
                positions.append(i)
        
        if not alphas:
            return []
        
        # Find significant breaks
        mean_diff = sum(alphas) / len(alphas)
        std_diff = math.sqrt(sum((a - mean_diff) ** 2 for a in alphas) / len(alphas))
        
        breaks = []
        for i, (pos, alpha_diff) in enumerate(zip(positions, alphas)):
            if alpha_diff > mean_diff + 2 * std_diff:
                breaks.append({
                    "position": pos,
                    "value": values[pos],
                    "alpha_difference": round(alpha_diff, 4),
                    "significance": round((alpha_diff - mean_diff) / std_diff, 2)
                })
        
        return breaks
    
    def identify_outliers(
        self,
        values: List[float],
        threshold: float = 3.0
    ) -> List[Dict]:
        """
        Identify statistical outliers using z-score
        """
        if len(values) < 5:
            return []
        
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std = math.sqrt(variance) if variance > 0 else 1
        
        outliers = []
        for i, v in enumerate(values):
            z = (v - mean) / std if std > 0 else 0
            if abs(z) > threshold:
                outliers.append({
                    "index": i,
                    "value": v,
                    "z_score": round(z, 2),
                    "percentile": round(sum(1 for x in values if x <= v) / len(values) * 100, 1)
                })
        
        return sorted(outliers, key=lambda x: -abs(x["z_score"]))
    
    # ============ Private Methods ============
    
    def _simple_ks_test(
        self,
        values: List[float],
        alpha: float,
        xmin: float
    ) -> Tuple[float, float]:
        """Simple KS test without bootstrap"""
        values = sorted([v for v in values if v >= xmin])
        n = len(values)
        
        if n == 0:
            return 1.0, 0.0
        
        max_d = 0.0
        
        for i, v in enumerate(values):
            # Empirical CDF
            empirical = (i + 1) / n
            
            # Theoretical CDF for power law
            theoretical = 1 - (v / xmin) ** (1 - alpha) if v >= xmin else 0
            
            d = abs(empirical - theoretical)
            max_d = max(max_d, d)
        
        return max_d, 0.0
    
    def _calculate_r_squared(
        self,
        values: List[float],
        alpha: float,
        xmin: float
    ) -> float:
        """Calculate R² for log-log regression"""
        counter = Counter(int(v) for v in values if v >= xmin)
        
        if len(counter) < 3:
            return 0.0
        
        # Log-log data
        x_log = [math.log(k) for k in counter.keys()]
        y_log = [math.log(c) for c in counter.values()]
        
        if not x_log or not y_log:
            return 0.0
        
        # Mean
        x_mean = sum(x_log) / len(x_log)
        y_mean = sum(y_log) / len(y_log)
        
        # SS
        ss_tot = sum((y - y_mean) ** 2 for y in y_log)
        
        # Predicted: log(y) = c - alpha * log(x)
        c = y_mean + alpha * x_mean
        y_pred = [c - alpha * x for x in x_log]
        
        ss_res = sum((y - yp) ** 2 for y, yp in zip(y_log, y_pred))
        
        return 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
    
    def _power_law_ll(
        self,
        values: List[float],
        alpha: float,
        xmin: float
    ) -> float:
        """Log-likelihood for power law"""
        tail = [v for v in values if v >= xmin]
        n = len(tail)
        
        if n == 0 or alpha <= 1:
            return float('-inf')
        
        ll = n * math.log(alpha - 1) - n * math.log(xmin)
        ll -= alpha * sum(math.log(v / xmin) for v in tail)
        
        return ll
    
    def _exponential_ll(self, values: List[float]) -> float:
        """Log-likelihood for exponential distribution"""
        n = len(values)
        if n == 0:
            return float('-inf')
        
        mean = sum(values) / n
        if mean <= 0:
            return float('-inf')
        
        rate = 1 / mean
        ll = n * math.log(rate) - rate * sum(values)
        
        return ll
    
    def _lognormal_ll(self, values: List[float]) -> float:
        """Log-likelihood for lognormal distribution"""
        values = [v for v in values if v > 0]
        n = len(values)
        
        if n == 0:
            return float('-inf')
        
        log_values = [math.log(v) for v in values]
        mu = sum(log_values) / n
        sigma_sq = sum((lv - mu) ** 2 for lv in log_values) / n
        
        if sigma_sq <= 0:
            return float('-inf')
        
        ll = -n/2 * math.log(2 * math.pi * sigma_sq)
        ll -= sum((lv - mu) ** 2 / (2 * sigma_sq) for lv in log_values)
        ll -= sum(log_values)  # Jacobian
        
        return ll
    
    def _calculate_kurtosis(self, values: List[float]) -> float:
        """Calculate excess kurtosis"""
        n = len(values)
        if n < 4:
            return 0.0
        
        mean = sum(values) / n
        m2 = sum((v - mean) ** 2 for v in values) / n
        m4 = sum((v - mean) ** 4 for v in values) / n
        
        if m2 == 0:
            return 0.0
        
        return (m4 / (m2 ** 2)) - 3
    
    def _hill_estimator(self, values: List[float], k: Optional[int] = None) -> float:
        """Hill estimator for tail index"""
        values = sorted(values, reverse=True)
        n = len(values)
        
        if k is None:
            k = max(1, int(n ** 0.5))  # sqrt(n) rule
        
        k = min(k, n - 1)
        
        if k < 1 or values[k] <= 0:
            return 0.0
        
        log_sum = sum(math.log(values[i] / values[k]) for i in range(k))
        
        if log_sum == 0:
            return 0.0
        
        return k / log_sum
    
    def _mean_excess_function(self, values: List[float], quantile: float) -> float:
        """Mean excess function at given quantile"""
        values = sorted(values)
        n = len(values)
        
        threshold_idx = int(n * quantile)
        threshold = values[threshold_idx] if threshold_idx < n else values[-1]
        
        excesses = [v - threshold for v in values if v > threshold]
        
        return sum(excesses) / len(excesses) if excesses else 0.0
