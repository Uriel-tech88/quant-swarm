#!/usr/bin/env python3
"""
Hierarchical Risk Parity (HRP) Optimizer — Portfolio Agent

Implements HRP portfolio optimization as described by Marcos López de Prado.
This is a free, open-source alternative to traditional mean-variance optimization
that uses hierarchical clustering to build robust, diversified portfolios.

Outputs: Portfolio weights, diversification metrics, and evidence files
"""
import numpy as np
import pandas as pd
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from scipy.cluster.hierarchy import linkage, dendrogram, to_tree
from scipy.spatial.distance import squareform
import matplotlib.pyplot as plt

# Configuration
PORTFOLIO_DIR = Path(__file__).resolve().parent
RESULTS_DIR = PORTFOLIO_DIR / "optimizations"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def get_cluster_var(cov: np.ndarray, items: List[int]) -> float:
    """
    Compute the variance of a cluster based on the covariance matrix.
    """
    cov_slice = cov[np.ix_(items, items)]
    weights = np.ones_like(items) / len(items)
    portfolio_variance = np.dot(np.dot(weights, cov_slice), weights.T)
    return portfolio_variance


def get_quasi_diag(link: np.ndarray) -> List[int]:
    """
    Get the quasi-diagonal representation of a linkage matrix.
    Uses scipy's leaves_list (dendrogram leaf order), which is exactly the
    quasi-diagonalization of López de Prado's HRP — robust for any n.
    """
    from scipy.cluster.hierarchy import leaves_list
    return [int(i) for i in leaves_list(link)]


def get_recursive_bisection(cov: np.ndarray, sorted_indices: List[int]) -> np.ndarray:
    """
    Recursively bisect the sorted indices to build the HRP weights.
    Standard mlfinlab algorithm: start every asset at weight 1, then split
    each cluster in half and redistribute by inverse relative cluster variance.
    """
    weights = np.ones(cov.shape[0])
    cluster_items = [list(sorted_indices)]
    while len(cluster_items) > 0:
        # split every cluster with >1 item into halves; singletons drop out
        cluster_items = [
            i[j:k]
            for i in cluster_items
            for j, k in ((0, len(i) // 2), (len(i) // 2, len(i)))
            if len(i) > 1
        ]
        for cluster in cluster_items:
            if len(cluster) < 2:
                continue  # singletons keep their inherited weight
            left_cluster = cluster[:len(cluster) // 2]
            right_cluster = cluster[len(cluster) // 2:]
            c_var_left = get_cluster_var(cov, left_cluster)
            c_var_right = get_cluster_var(cov, right_cluster)
            alpha = 1 - c_var_left / (c_var_left + c_var_right)
            weights[left_cluster] *= alpha
            weights[right_cluster] *= 1 - alpha
    return weights


def compute_hrp_weights(
    returns: pd.DataFrame,
    method: str = "single",
    metric: str = "euclidean",
) -> Tuple[np.ndarray, pd.DataFrame, Dict]:
    """
    Compute Hierarchical Risk Parity weights from asset returns.

    Args:
        returns: DataFrame of asset returns (time x assets)
        method: Linkage method for hierarchical clustering
        metric: Distance metric for clustering

    Returns:
        weights: Array of HRP weights
        corr_matrix: Correlation matrix
        diagnostics: Dictionary with clustering and diversification metrics
    """
    # Compute correlation and covariance
    corr = returns.corr()
    cov = returns.cov()

    # Convert correlation to distance matrix
    distance = np.sqrt(0.5 * (1 - corr))
    # Perform hierarchical clustering
    linkage_matrix = linkage(squareform(distance), method=method, metric=metric)

    # Get quasi-diagonal sort
    sorted_indices = get_quasi_diag(linkage_matrix)
    sorted_labels = [returns.columns[i] for i in sorted_indices]

    # Compute HRP weights
    hrp_weights = get_recursive_bisection(cov.values, sorted_indices)
    hrp_weights = hrp_weights / hrp_weights.sum()  # normalize

    # Calculate diagnostics
    portfolio_variance = np.dot(np.dot(hrp_weights, cov.values), hrp_weights.T)
    effective_assets = 1 / np.sum(hrp_weights**2)
    max_weight = np.max(hrp_weights)
    min_weight = np.min(hrp_weights)
    weight_concentration = max_weight - min_weight

    diagnostics = {
        "method": method,
        "metric": metric,
        "n_assets": len(returns.columns),
        "effective_assets": effective_assets,
        "max_weight": float(max_weight),
        "min_weight": float(min_weight),
        "weight_concentration": float(weight_concentration),
        "portfolio_variance": float(portfolio_variance),
        "annualized_volatility": float(np.sqrt(portfolio_variance * 252)),
        "diversification_ratio": float(np.sqrt(np.sum(hrp_weights**2 * np.diag(cov.values))) / np.sqrt(portfolio_variance)),
        "timestamp": pd.Timestamp.now().isoformat(),
    }

    return hrp_weights, corr, diagnostics


def save_hrp_results(
    weights: np.ndarray,
    asset_names: List[str],
    corr_matrix: pd.DataFrame,
    diagnostics: Dict,
    output_dir: Path = RESULTS_DIR,
) -> Dict[str, Path]:
    """
    Save HRP optimization results to files.
    """
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    file_paths = {}

    # 1. Portfolio weights CSV
    weights_df = pd.DataFrame({
        "asset": asset_names,
        "weight": weights,
        "weight_pct": weights * 100
    }).sort_values("weight", ascending=False)
    weights_path = output_dir / f"hrp_weights_{timestamp}.csv"
    weights_df.to_csv(weights_path, index=False)
    file_paths["weights"] = weights_path

    # 2. Correlation matrix heatmap (as CSV and optionally PNG)
    corr_path = output_dir / f"correlation_matrix_{timestamp}.csv"
    corr_matrix.to_csv(corr_path)
    file_paths["correlation"] = corr_path

    # 3. Diagnostics JSON
    diag_path = output_dir / f"hrp_diagnostics_{timestamp}.json"
    with open(diag_path, "w") as f:
        json.dump(diagnostics, f, indent=2)
    file_paths["diagnostics"] = diag_path

    # 4. Summary report
    report_path = output_dir / f"hrp_report_{timestamp}.md"
    report = f"""
# Hierarchical Risk Parity (HRP) Portfolio Optimization Report

Generated: {pd.Timestamp.now().isoformat()}

## Portfolio Composition

| Asset | Weight (%) |
|-------|------------|
"""
    for asset, weight in zip(asset_names, weights):
        report += f"| {asset} | {weight*100:6.2f}% |\n"

    report += f"""
## Diversification Metrics

- **Effective Number of Assets**: {diagnostics['effective_assets']:.2f}
- **Maximum Weight**: {diagnostics['max_weight']*100:.2f}%
- **Minimum Weight**: {diagnostics['min_weight']*100:.2f}%
- **Weight Concentration (Max-Min)**: {diagnostics['weight_concentration']*100:.2f}%
- **Portfolio Variance**: {diagnostics['portfolio_variance']:.6f}
- **Annualized Volatility**: {diagnostics['annualized_volatility']*100:.2f}%
- **Diversification Ratio**: {diagnostics['diversification_ratio']:.3f}

## Clustering Configuration

- **Linkage Method**: {diagnostics['method']}
- **Distance Metric**: {diagnostics['metric']}
- **Number of Assets**: {diagnostics['n_assets']}

## Notes

HRP builds a portfolio by:
1. Computing asset correlation matrix
2. Applying hierarchical clustering to group similar assets
3. Recursively bisecting clusters and allocating capital inversely proportional to cluster variance
4. Results in a well-diversified portfolio without requiring expected returns

All calculations use free, open-source libraries (NumPy, SciPy, pandas).
"""
    with open(report_path, "w") as f:
        f.write(report)
    file_paths["report"] = report_path

    return file_paths


def generate_sample_returns(
    n_assets: int = 5,
    n_observations: int = 252,
    asset_names: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Generate synthetic asset returns for demonstration/testing.
    """
    if asset_names is None:
        asset_names = [f"ASSET_{i+1}" for i in range(n_assets)]

    # Generate correlated returns
    np.random.seed(42)  # for reproducibility
    mean_returns = np.random.uniform(0.0001, 0.001, n_assets)  # daily returns
    # Create a factor structure for correlations
    factor_loadings = np.random.uniform(0.5, 1.5, (n_assets, 3))
    factor_returns = np.random.normal(0, 0.01, (n_observations, 3))
    specific_returns = np.random.normal(0, 0.005, (n_observations, n_assets))
    returns = np.dot(factor_returns, factor_loadings.T) + specific_returns + mean_returns

    returns_df = pd.DataFrame(returns, columns=asset_names)
    returns_df.index = pd.date_range(
        end=pd.Timestamp.now(), periods=n_observations, freq="D"
    )
    return returns_df


def run_hrp_optimization(
    returns: Optional[pd.DataFrame] = None,
    asset_names: Optional[List[str]] = None,
) -> Dict:
    """
    Main function to run HRP optimization and save results.
    """
    print("=== Hierarchical Risk Parity (HRP) Optimization ===")

    if returns is None:
        print("Generating sample returns for demonstration...")
        returns = generate_sample_returns(
            n_assets=5,
            n_observations=252,
            asset_names=["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD"],
        )
        print(f"Generated returns shape: {returns.shape}")
        print(f"Assets: {list(returns.columns)}")

    # Compute HRP weights
    weights, corr_matrix, diagnostics = compute_hrp_weights(returns)

    # Save results
    file_paths = save_hrp_results(weights, list(returns.columns), corr_matrix, diagnostics)

    # Print summary
    print(f"\n✓ HRP Optimization Complete!")
    print(f"  Assets: {len(returns.columns)}")
    print(f"  Effective Assets: {diagnostics['effective_assets']:.2f}")
    print(f"  Max Weight: {diagnostics['max_weight']*100:.2f}%")
    print(f"  Min Weight: {diagnostics['min_weight']*100:.2f}%")
    print(f"  Annualized Volatility: {diagnostics['annualized_volatility']*100:.2f}%")
    print(f"\nResults saved to: {RESULTS_DIR}/")
    for name, path in file_paths.items():
        print(f"  - {path.name}")

    return {
        "weights": weights,
        "asset_names": list(returns.columns),
        "correlation_matrix": corr_matrix,
        "diagnostics": diagnostics,
        "file_paths": {k: str(v) for k, v in file_paths.items()},
    }


if __name__ == "__main__":
    import sys
    if "--check" in sys.argv:
        print("HRP Optimizer: Dependencies loaded successfully")
        print("✓ NumPy, SciPy, pandas available")
        print("✓ Output directory accessible")
        sys.exit(0)

    # Run HRP optimization with sample data
    run_hrp_optimization()
