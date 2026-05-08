"""
Batter Clustering Module
Segments batters by tendency patterns and provides cluster-based insights.
"""

import json
import os
import numpy as np
import pandas as pd


def load_batter_clusters(path):
    """Load batter cluster assignments from JSON file."""
    if not os.path.exists(path):
        return {}

    with open(path, "r") as f:
        return json.load(f)


def get_batter_cluster(batter_id, batter_clusters_data):
    """Get cluster assignment for a batter."""
    if not batter_clusters_data:
        return None

    batter_str = str(batter_id)
    return batter_clusters_data.get(batter_str)


def describe_cluster(cluster_id, cluster_descriptions=None):
    """Return human-readable description of a cluster."""
    if cluster_descriptions is None:
        cluster_descriptions = {
            0: "Aggressive contact hitter",
            1: "Disciplined approach",
            2: "Strikeout-prone",
            3: "High-contact defender",
            4: "Selective hitter",
        }

    return cluster_descriptions.get(cluster_id, f"Cluster {cluster_id}")


def get_location_effectiveness_vs_cluster(
    pitch_type,
    plate_loc_height,
    plate_loc_side,
    batter_cluster,
    cluster_effectiveness_data=None,
):
    """
    Get expected Location+ effectiveness for a batter cluster.

    This can be used to refine Location+ predictions based on:
    - How effective is this location against this type of batter?
    - Different batters may be vulnerable to different locations.

    Args:
        pitch_type: Pitch type
        plate_loc_height: Pitch vertical location
        plate_loc_side: Pitch horizontal location
        batter_cluster: Batter cluster ID
        cluster_effectiveness_data: Optional dict of cluster-specific effectiveness data

    Returns:
        Adjustment factor (0-1) representing effectiveness vs this cluster, or None
    """
    if cluster_effectiveness_data is None or not cluster_effectiveness_data:
        return None

    key = f"{pitch_type}_{batter_cluster}"
    return cluster_effectiveness_data.get(key)


def get_batter_whiff_tendency(batter_id, batter_stats_data=None):
    """
    Get a batter's overall whiff tendency.

    Can be used to normalize Location+ predictions:
    - High-whiff batters will have higher whiff rates at any location
    - Low-whiff batters are more selective

    Args:
        batter_id: Batter identifier
        batter_stats_data: Optional dict of per-batter whiff statistics

    Returns:
        Whiff rate (0-1) or None if not available
    """
    if batter_stats_data is None or not batter_stats_data:
        return None

    batter_str = str(batter_id)
    return batter_stats_data.get(batter_str)


# Cluster descriptions (can be customized based on actual cluster characteristics)
CLUSTER_NAMES = {
    0: "Contact Hitter",
    1: "Disciplined Approach",
    2: "Strikeout-Prone",
    3: "High-Contact Defender",
    4: "Selective",
}
