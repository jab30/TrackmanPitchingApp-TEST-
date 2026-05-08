"""
Pitcher Adjustment Module
Applies pitcher-specific location effectiveness adjustments to Location+ scores.
"""

import json
import os
import numpy as np


def load_pitcher_adjustments(path):
    """Load pitcher adjustment data from JSON file."""
    if not os.path.exists(path):
        return {}

    with open(path, "r") as f:
        return json.load(f)


def get_location_bin(height, side, bin_size=0.2):
    """Bin plate location to nearest bin_size."""
    height_bin = (height // bin_size * bin_size)
    side_bin = (side // bin_size * bin_size)
    return f"{height_bin:.1f}_{side_bin:.1f}"


def adjust_location_plus(
    location_plus,
    pitcher_id,
    pitch_type,
    plate_loc_height,
    plate_loc_side,
    pitcher_adjustments_data,
    min_pitcher_pitches=50,
    adjustment_scale=1.0,
):
    """
    Apply pitcher-specific adjustment to Location+ score.

    Args:
        location_plus: Base Location+ value
        pitcher_id: Pitcher identifier
        pitch_type: Pitch type (e.g., "Fastball", "Slider")
        plate_loc_height: Pitch vertical location
        plate_loc_side: Pitch horizontal location
        pitcher_adjustments_data: Dict of pitcher adjustments loaded from JSON
        min_pitcher_pitches: Minimum pitches before applying adjustment
        adjustment_scale: Scale factor for adjustment magnitude (0-1, higher = more adjustment)

    Returns:
        Adjusted Location+ value (or original if no adjustment available)
    """
    if not pitcher_adjustments_data:
        return location_plus

    if np.isnan(location_plus) or pd.isna(location_plus):
        return location_plus

    pitcher_str = str(pitcher_id)

    # Check if pitcher exists in adjustments
    if pitcher_str not in pitcher_adjustments_data:
        return location_plus

    pitcher_adj = pitcher_adjustments_data[pitcher_str]

    # Check if pitch type exists for this pitcher
    if pitch_type not in pitcher_adj:
        return location_plus

    location_bins = pitcher_adj[pitch_type]

    # Get bin for this location
    location_bin = get_location_bin(plate_loc_height, plate_loc_side)

    if location_bin not in location_bins:
        return location_plus

    # Get adjustment delta and apply
    delta = location_bins[location_bin]
    adjustment = delta * 10 * adjustment_scale  # Scale delta to Location+ scale

    return location_plus + adjustment


# Import pandas for isna check - add at top of file if not already imported
import pandas as pd
