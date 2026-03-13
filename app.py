import os
import glob
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.patches import Ellipse
from shiny import App, ui, reactive, render
import io
import base64
from datetime import date

# Addd this after the imports section
SORTABLE_TABLE_JS = """
<script>
function makeSortable(tableId) {
    const table = document.getElementById(tableId);
    if (!table || table.dataset.sortableInitialized) return;
    // Mark as initialized to prevent duplicate event listeners
    table.dataset.sortableInitialized = 'true';
    // Store original row order
    const tbody = table.querySelector('tbody');
    const originalRows = Array.from(tbody.querySelectorAll('tr')).map((row, index) => ({
        row: row.cloneNode(true),
        originalIndex: index
    }));
    table.dataset.originalRows = JSON.stringify(originalRows.map(item => item.originalIndex));
    const headers = table.querySelectorAll('th');
    headers.forEach((header, index) => {
        header.style.cursor = 'pointer';
        header.style.userSelect = 'none';
        // Remove any existing click listeners
        header.onclick = null;
        let clickCount = 0;
        let clickTimer = null;
        header.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            clickCount++;
            if (clickCount === 1) {
                // Start timer for double-click detection
                clickTimer = setTimeout(() => {
                    // Single click - sort normally
                    sortTable(tableId, index);
                    clickCount = 0;
                }, 300); // 300ms window for double-click
            } else if (clickCount === 2) {
                // Double click - reset to original order
                clearTimeout(clickTimer);
                resetToOriginalOrder(tableId);
                clickCount = 0;
            }
        });
    });
}
function sortTable(tableId, columnIndex) {
    const table = document.getElementById(tableId);
    if (!table) return;
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    // Get the header that was clicked
    const headers = table.querySelectorAll('th');
    const clickedHeader = headers[columnIndex];
    // Determine sort direction - check for existing sort class
    const isCurrentlyAsc = clickedHeader.classList.contains('sort-asc');
    const isCurrentlyDesc = clickedHeader.classList.contains('sort-desc');
    let sortAscending;
    if (!isCurrentlyAsc && !isCurrentlyDesc) {
        // First click - sort ascending
        sortAscending = true;
    } else if (isCurrentlyAsc) {
        // Currently ascending - switch to descending
        sortAscending = false;
    } else {
        // Currently descending - switch to ascending
        sortAscending = true;
    }
    // Remove sort indicators from ALL headers
    headers.forEach(header => {
        header.classList.remove('sort-asc', 'sort-desc');
        // Clean up the header text
        const textContent = header.textContent || header.innerText;
        header.innerHTML = textContent.replace(' ↑', '').replace(' ↓', '').replace(' ⟲', '');
    });
    // Add sort indicator to clicked header
    clickedHeader.classList.add(sortAscending ? 'sort-asc' : 'sort-desc');
    const cleanText = (clickedHeader.textContent || clickedHeader.innerText).replace(' ↑', '').replace(' ↓', '').replace(' ⟲', '');
    clickedHeader.innerHTML = cleanText + (sortAscending ? ' ↑' : ' ↓');
    // Sort the rows
    rows.sort((a, b) => {
        const aValue = (a.cells[columnIndex].textContent || a.cells[columnIndex].innerText).trim();
        const bValue = (b.cells[columnIndex].textContent || b.cells[columnIndex].innerText).trim();
        // Handle numeric values
        const aNum = parseFloat(aValue);
        const bNum = parseFloat(bValue);
        let comparison = 0;
        if (!isNaN(aNum) && !isNaN(bNum)) {
            comparison = aNum - bNum;
        } else {
            comparison = aValue.localeCompare(bValue);
        }
        return sortAscending ? comparison : -comparison;
    });
    // Re-append sorted rows
    rows.forEach(row => tbody.appendChild(row));
}
function resetToOriginalOrder(tableId) {
    const table = document.getElementById(tableId);
    if (!table) return;
    const tbody = table.querySelector('tbody');
    const currentRows = Array.from(tbody.querySelectorAll('tr'));
    // Remove sort indicators from ALL headers and add reset indicator
    const headers = table.querySelectorAll('th');
    headers.forEach(header => {
        header.classList.remove('sort-asc', 'sort-desc');
        const textContent = header.textContent || header.innerText;
        const cleanText = textContent.replace(' ↑', '').replace(' ↓', '').replace(' ⟲', '');
        header.innerHTML = cleanText;
    });
    // Add reset indicator to first header temporarily
    const firstHeader = headers[0];
    if (firstHeader) {
        const cleanText = (firstHeader.textContent || firstHeader.innerText).replace(' ↑', '').replace(' ↓', '').replace(' ⟲', '');
        firstHeader.innerHTML = cleanText + ' ⟲';
        // Remove the reset indicator after 1 second
        setTimeout(() => {
            const currentText = firstHeader.textContent || firstHeader.innerText;
            firstHeader.innerHTML = currentText.replace(' ⟲', '');
        }, 1000);
    }
    // Sort rows back to original order based on their original position
    const rowsWithOriginalData = currentRows.map(row => {
        // Try to find original index by matching the first cell content or row data
        const firstCellText = (row.cells[0].textContent || row.cells[0].innerText).trim();
        let originalIndex = -1;
        // For pitch type tables, use the pitch type to maintain order
        if (firstCellText === 'TOTAL') {
            originalIndex = 999; // TOTAL should always be last
        } else {
            // Try to maintain relative order based on content
            const pitchTypeOrder = ['Fastball', 'Sinker', 'Cutter', 'Changeup', 'ChangeUp', 'Slider', 'Sweeper', 'Curveball', 'Splitter'];
            const foundIndex = pitchTypeOrder.indexOf(firstCellText);
            originalIndex = foundIndex >= 0 ? foundIndex : currentRows.indexOf(row);
        }
        return { row, originalIndex };
    });
    // Sort by original index
    rowsWithOriginalData.sort((a, b) => a.originalIndex - b.originalIndex);
    // Re-append rows in original order
    rowsWithOriginalData.forEach(item => tbody.appendChild(item.row));
}
// Initialize tables when DOM is ready
function initializeTables() {
    document.querySelectorAll('table[id*="table"]').forEach(table => {
        if (table.id) {
            makeSortable(table.id);
        }
    });
}
// Run initialization
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeTables);
} else {
    initializeTables();
}
// Auto-initialize new tables
const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
        mutation.addedNodes.forEach((node) => {
            if (node.nodeType === 1) {
                if (node.tagName === 'TABLE' && node.id && node.id.includes('table')) {
                    setTimeout(() => makeSortable(node.id), 50);
                }
                const tables = node.querySelectorAll ? node.querySelectorAll('table[id*="table"]') : [];
                tables.forEach(table => {
                    if (table.id) {
                        setTimeout(() => makeSortable(table.id), 50);
                    }
                });
            }
        });
    });
});
observer.observe(document.body, { childList: true, subtree: true });
</script>
<style>
th {
    position: relative;
}
th:hover {
    background-color: #e9ecef !important;
}
.sort-asc, .sort-desc {
    background-color: #dee2e6 !important;
}
</style>
"""

# Import your existing functions (with fallback if not available)
try:
    from functions import arm_angle_calc, convert_to_inches, arm_angle_categories, pitch_colors
except ImportError:
    # Fallback functions if functions.py doesn't exist
    def arm_angle_calc(df, rosters):
        return df


    def convert_to_inches(height_str):
        if pd.isna(height_str):
            return np.nan
        try:
            if "'" in str(height_str):
                parts = str(height_str).replace('"', '').split("'")
                feet = int(parts[0])
                inches = int(parts[1]) if len(parts) > 1 else 0
                return feet * 12 + inches
        except:
            return np.nan
        return np.nan


    def arm_angle_categories(df):
        return df


    def pitch_colors():
        return {}

# Load CSV files
csv_folder = "TrackmanCSV's"
csv_paths = glob.glob(os.path.join(csv_folder, "*.csv"))

if not csv_paths:
    # Create dummy data for testing if no CSV files found
    print(f"No CSV files found in '{csv_folder}' folder. Creating dummy data.")
    df = pd.DataFrame({
        'Pitcher': ['John Smith', 'Jane Doe', 'Bob Johnson'] * 50,
        'PitchType': ['Fastball', 'Slider', 'Changeup'] * 50,
        'TaggedPitchType': ['Fastball', 'Slider', 'ChangeUp'] * 50,
        'RelSpeed': np.random.normal(90, 5, 150),
        'InducedVertBreak': np.random.normal(15, 5, 150),
        'HorzBreak': np.random.normal(0, 8, 150),
        'SpinRate': np.random.normal(2400, 200, 150),
        'RelHeight': np.random.normal(6, 0.5, 150),
        'RelSide': np.random.normal(0, 0.5, 150),
        'Extension': np.random.normal(6.2, 0.3, 150),
        'PlateLocSide': np.random.normal(0, 1, 150),
        'PlateLocHeight': np.random.normal(2.5, 0.8, 150),
        'PitchCall': np.random.choice(['StrikeCalled', 'BallCalled', 'StrikeSwinging', 'FoulBall', 'InPlay'], 150),
        'Date': pd.date_range('2024-01-01', periods=150, freq='D'),
        'BatterSide': np.random.choice(['Left', 'Right'], 150),
        'PitcherTeam': ['KEN_OWL'] * 150,
        'VertApprAngle': np.random.normal(-5, 2, 150),
        'HorzApprAngle': np.random.normal(0, 1, 150),
        'VertRelAngle': np.random.normal(-2, 1, 150),
        'HorzRelAngle': np.random.normal(0, 0.5, 150),
        'ExitSpeed': np.random.normal(85, 10, 150),
        'Angle': np.random.normal(15, 10, 150),
        'PitchofPA': np.random.choice([1, 2, 3, 4, 5], 150),
        'Tilt': ['10:30', '11:00', '1:30'] * 50
    })
else:
    df_list = []
    for path in csv_paths:
        try:
            df_temp = pd.read_csv(path, parse_dates=["Date"])
            df_list.append(df_temp)
        except Exception as e:
            print(f"Error loading {path}: {e}")

    if df_list:
        df = pd.concat(df_list, ignore_index=True)
    else:
        raise RuntimeError("All CSVs failed to load.")

if df.empty:
    raise RuntimeError("No data available.")

# Drop rows missing HorzBreak if column exists
if "HorzBreak" in df.columns:
    df = df.dropna(subset=["HorzBreak"])

# Clean and convert Tilt column if it exists
if "Tilt" in df.columns:
    def clock_to_degrees(clock_str):
        if pd.isna(clock_str) or clock_str == "" or clock_str is None:
            return np.nan
        try:
            parts = str(clock_str).strip().split(":")
            if len(parts) == 2:
                hours = int(parts[0])
                minutes = int(parts[1])
                total_minutes = (hours % 12) * 60 + minutes
                degrees = (total_minutes / 720) * 360
                return degrees
            else:
                return np.nan
        except (ValueError, TypeError):
            return np.nan


    df["Tilt"] = df["Tilt"].apply(clock_to_degrees)

# Load rosters if available
try:
    rosters = pd.read_csv("rosters.csv")
    rosters = rosters.rename(columns={"Name": "NAME", "Ht": "Ht_raw"})
    rosters["height_inches"] = rosters["Ht_raw"].apply(convert_to_inches)
    rosters["POSITION"] = "P"
except:
    rosters = pd.DataFrame()

# Apply arm angle calculations
if all(col in df.columns for col in ['RelSide', 'RelHeight']) and not rosters.empty:
    df = arm_angle_calc(df, rosters)
    df = arm_angle_categories(df)

# Create calculated fields
if "TaggedPitchType" in df.columns:
    df["PitchType"] = df["TaggedPitchType"].replace({
        "Four-Seam": "Fastball", "Fastball": "Fastball",
        "Sinker": "Sinker", "Slider": "Slider",
        "Sweeper": "Sweeper", "Curveball": "Curveball",
        "ChangeUp": "Changeup", "Splitter": "Splitter",
        "Cutter": "Cutter"
    }).fillna("Unknown")

if "PitchType" not in df.columns:
    df["PitchType"] = "Unknown"

if "Pitcher" in df.columns:
    df["Pitcher"] = df["Pitcher"].str.replace(r"(\w+), (\w+)", r"\2 \1", regex=True)

if "PlateLocHeight" in df.columns and "PlateLocSide" in df.columns:
    df["inZone"] = np.where(
        (df["PlateLocHeight"].between(1.6, 3.5)) &  # Slightly wider height range
        (df["PlateLocSide"].between(-1, 1)), 1, 0  # Slightly wider horizontal range (17 inches / 12 / 2)
    )
    # DIAGNOSTIC: Print zone statistics
    print(f"\nStrike Zone Diagnostic:")
    print(f"Total pitches: {len(df)}")
    print(f"Pitches in zone: {df['inZone'].sum()}")
    print(f"Zone%: {(df['inZone'].sum() / len(df) * 100):.1f}%")
    print(f"\nPlateLocHeight range: {df['PlateLocHeight'].min():.2f} to {df['PlateLocHeight'].max():.2f}")
    print(f"PlateLocSide range: {df['PlateLocSide'].min():.2f} to {df['PlateLocSide'].max():.2f}")

if "PitchCall" in df.columns and "inZone" in df.columns:
    df["Chase"] = np.where(
        (df["inZone"] == 0) &
        (df["PitchCall"].isin(["FoulBall", "FoulBallNotFieldable", "InPlay", "StrikeSwinging"])), 1, 0
    )

if "Date" in df.columns:
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    if "AwayTeam" in df.columns and "HomeTeam" in df.columns:
        df["CustomGameID"] = (
                df["Date"].dt.strftime("%Y-%m-%d") + ": " +
                df["AwayTeam"].str[:3] + " @ " + df["HomeTeam"].str[:3]
        )

# Build pitcher list
all_pitchers = sorted(df[df["PitcherTeam"] == "KEN_OWL"]["Pitcher"].dropna().unique().tolist())

# Date ranges
if "Date" in df.columns and not df["Date"].isna().all():
    min_date = df["Date"].min().date()
    max_date = df["Date"].max().date()
else:
    min_date = max_date = date.today()

# Batter sides
if "BatterSide" in df.columns:
    unique_batter_sides = sorted(df["BatterSide"].dropna().unique().tolist())
else:
    unique_batter_sides = []

# Pitch types for leaderboard
all_pitch_types = ["TOTAL"] + sorted([pt for pt in df["PitchType"].unique() if pt != "Unknown"])

# Color palettes
pitch_colors_dict = {
    "Fastball": "#ff007d", "Four-Seam": "#ff007d", "Sinker": "#98165D",
    "Slider": "#67E18D", "Sweeper": "#1BB999", "Curveball": "#3025CE",
    "ChangeUp": "#F79E70", "Changeup": "#F79E70", "Splitter": "#90EE32", "Cutter": "#BE5FA0",
    "Undefined": "#9C8975", "PitchOut": "#472C30"
}

arm_angle_colors = {
    'Overhand': '#FF6B6B',
    'High Three-Quarters': '#4ECDC4',
    'Low Three-Quarters': '#45B7D1',
    'Sidearm': '#96CEB4',
    'Submarine': '#FFEAA7'
}

stat_ranges = {
    'Fastball': {
        'Vel': (84, 96, 90),
        'Extension': (5.35, 7.0, 6.07),
        'Zone%': (38.3, 57.8, 49.2),
        'Chase%': (15, 30, 22.5),
        'Miss%': (15, 32, 22.5),
        'xWOBA': (0.130, 0.510, 0.314)
    },
    'Sinker': {
        'Vel': (84, 94, 90),
        'Extension': (5.35, 7.0, 6.07),
        'Zone%': (38.3, 57.8, 49.2),
        'Chase%': (13.9, 34, 23.1),
        'Miss%': (7, 27.4, 16.1),
        'xWOBA': (0.178, 0.410, 0.303)
    },
    'Cutter': {
        'Vel': (80.5, 90, 85.1),
        'Extension': (5.35, 7.0, 6.07),
        'Zone%': (38.3, 57.8, 49.2),
        'Chase%': (11, 48, 29.2),
        'Miss%': (10, 52, 29.2),
        'xWOBA': (0.160, 0.450, 0.240)
    },
    'Changeup': {
        'Vel': (76.1, 87, 80.9),
        'Extension': (5.35, 7.0, 6.07),
        'Zone%': (29, 48.4, 36.2),
        'Chase%': (15, 50, 32),
        'Miss%': (11.6, 58, 34.4),
        'xWOBA': (0.126, 0.480, 0.229)
    },
    'ChangeUp': {
        'Vel': (76.1, 87, 80.9),
        'Extension': (5.35, 7.0, 6.07),
        'Zone%': (29, 48.4, 36.2),
        'Chase%': (15, 50, 32),
        'Miss%': (11.6, 58, 34.4),
        'xWOBA': (0.126, 0.480, 0.229)
    },
    'Splitter': {
        'Vel': (77, 87.9, 81.8),
        'Extension': (5.35, 7.0, 6.07),
        'Zone%': (35, 50.4, 44.2),
        'Chase%': (11, 49, 31.2),
        'Miss%': (9.7, 63.6, 39.1),
        'xWOBA': (0.140, 0.350, 0.199)
    },
    'Slider': {
        'Vel': (76, 88, 80.2),
        'Extension': (5.35, 7.0, 6.07),
        'Zone%': (29, 50.4, 40.2),
        'Chase%': (13, 46, 27.5),
        'Miss%': (30, 45, 33.8),
        'xWOBA': (0.140, 0.450, 0.241)
    },
    'Sweeper': {
        'Vel': (76, 86, 81),
        'Extension': (5.35, 7.0, 6.07),
        'Zone%': (29, 50.4, 40.2),
        'Chase%': (30, 45, 37.5),
        'Miss%': (16.5, 60, 37.5),
        'xWOBA': (0.140, 0.455, 0.241)
    },
    'Curveball': {
        'Vel': (73, 82, 77),
        'Extension': (5.35, 7.0, 6.07),
        'Zone%': (29, 50.4, 40.2),
        'Chase%': (25, 36, 24),
        'Miss%': (14, 54, 32.8),
        'xWOBA': (0.125, 0.400, 0.221)
    }
}

# Gradient coloring function
def get_performance_color(value, pitch_type, metric):
    if pd.isna(value):
        return "background-color: #f8f9fa; color: #333;"

    if metric == 'LaunchAng':
        if -190 <= value <= 12:
            return "background-color: #dc3545; color: white; font-weight: bold;"
        elif 12 < value <= 18:
            return "background-color: #f8f9fa; color: #333;"
        elif 25 <= value <= 31:
            return "background-color: #007bff; color: white; font-weight: bold;"
        elif value >= 40:
            return "background-color: #dc3545; color: white; font-weight: bold;"
        else:
            return "background-color: #f8f9fa; color: #333;"

    if metric == 'ExitVel':
        min_val, max_val = 81.5, 90
        normalized = 1 - ((value - min_val) / (max_val - min_val)) if max_val > min_val else 0.5
        normalized = max(0, min(1, normalized))
    else:
        # Use stat_ranges if available
        if pitch_type in stat_ranges and metric in stat_ranges[pitch_type]:
            pitch_stats = stat_ranges[pitch_type][metric]
            min_val, max_val = pitch_stats[0], pitch_stats[1]
        else:
            default_ranges = {
                '1PK%': (54, 68),
                '2of3%': (30, 85),
                'Zone%': (39, 54.4),
                'IZWhiff%': (9.5, 22.5),
                'Miss%': (13.5, 32),
                'SwStr%': (6, 15),
                'Strike%': (58.5, 68),
                'GB%': (35, 60),
                'LD%': (15, 25),
                'FB%': (25, 45)
            }
            if metric in default_ranges:
                min_val, max_val = default_ranges[metric]
            else:
                return "background-color: #f8f9fa; color: #333;"

        normalized = (value - min_val) / (max_val - min_val) if max_val > min_val else 0.5
        normalized = max(0, min(1, normalized))

    # Create gradient color
    val = max(0, min(1, normalized))

    if val < 0.5:
        factor = val * 2
        r = int(0 + (248 - 0) * factor)
        g = int(123 + (249 - 123) * factor)
        b = int(255 + (250 - 255) * factor)
        text_color = "white" if val < 0.2 else "#333"
        font_weight = "bold" if val < 0.3 else "normal"
    else:
        factor = (val - 0.5) * 2
        r = int(248 + (220 - 248) * factor)
        g = int(249 + (53 - 249) * factor)
        b = int(250 + (69 - 250) * factor)
        text_color = "#333" if val < 0.7 else "white"
        font_weight = "normal" if val < 0.7 else "bold"

    return f"background-color: rgb({r}, {g}, {b}); color: {text_color}; font-weight: {font_weight};"


# Add these RIGHT AFTER the get_performance_color() function ends

def parse_stat_with_percentile(stat_str):
    """
    Parse a stat string like '23.0% (88%)' into value and percentile.
    Returns: (value, percentile)
    """
    if pd.isna(stat_str) or stat_str == "" or stat_str == 0:
        return (0.0, 0.0)

    try:
        stat_str = str(stat_str)
        # Extract value and percentile
        if '(' in stat_str and ')' in stat_str:
            value_part = stat_str.split('(')[0].strip().replace('%', '')
            percentile_part = stat_str.split('(')[1].split(')')[0].strip().replace('%', '').replace('tile', '')
            return (float(value_part), float(percentile_part))
        else:
            # No percentile available, just return value
            value = float(stat_str.replace('%', ''))
            return (value, 50.0)  # Default to 50th percentile if not provided
    except:
        return (0.0, 0.0)


def get_percentile_color(value, percentile, stat_name):
    """
    Color code stats based on their percentile ranking.

    Args:
        value: The actual stat value
        percentile: The percentile (0-100) from the CSV
        stat_name: Name of the stat for determining if lower/higher is better

    Returns:
        CSS style string for the cell
    """
    if pd.isna(value) or pd.isna(percentile):
        return "background-color: #f8f9fa; color: #333;"

    # Stats where LOWER is better
    lower_is_better = ['BB%', 'FIP', 'Barrel%', 'HardHit%', 'BAA', 'wOBA']

    # For lower-is-better stats, invert the percentile
    if stat_name in lower_is_better:
        normalized = 1 - (percentile / 100)
    else:  # K% - higher is better
        normalized = percentile / 100

    normalized = max(0, min(1, normalized))

    # Create gradient color (blue to white to red)
    if normalized < 0.5:
        # Blue to white gradient (bad to neutral)
        factor = normalized * 2
        r = int(0 + (248 - 0) * factor)
        g = int(123 + (249 - 123) * factor)
        b = int(255 + (250 - 255) * factor)
        text_color = "white" if normalized < 0.2 else "#333"
        font_weight = "bold" if normalized < 0.3 else "normal"
    else:
        # White to red gradient (neutral to good)
        factor = (normalized - 0.5) * 2
        r = int(248 + (220 - 248) * factor)
        g = int(249 + (53 - 249) * factor)
        b = int(250 + (69 - 250) * factor)
        text_color = "#333" if normalized < 0.7 else "white"
        font_weight = "normal" if normalized < 0.7 else "bold"

    return f"background-color: rgb({r}, {g}, {b}); color: {text_color}; font-weight: {font_weight};"


def format_summary_stat(col, value):
    """Format summary stat values consistently"""
    if pd.isna(value):
        return "0.0"
    elif isinstance(value, (int, float)):
        if col in ["BAA", "wOBA"]:
            return f"{value:.3f}"
        elif col == "FIP":
            return f"{value:.2f}"
        else:
            return f"{value:.1f}"
    else:
        return str(value)

def get_summary_stat_color(value, stat_name):
    """Color code summary stats based on typical ranges"""
    if pd.isna(value):
        return "background-color: #f8f9fa; color: #333;"

    # Define ranges: (min, max, lower_is_better)
    stat_ranges = {
        'K%': (15, 30, False),  # (min, max, lower_is_better)
        'BB%': (5, 16, True),  # Lower BB% is better
        'FIP': (2.8, 6.5, True),  # Lower FIP is better
        'Barrel%': (4, 20, True),  # Lower Barrel% is better
        'HardHit%': (30, 45, True),  # Lower HardHit% is better
        'BAA': (0.200, 0.350, True),  # Lower BAA is better
        'wOBA': (0.220, 0.380, True)  # Lower wOBA is better
    }

    # Check if stat_name is valid FIRST
    if stat_name not in stat_ranges:
        return "background-color: #f8f9fa; color: #333;"

    # Get the stat range info
    min_val, max_val, lower_is_better = stat_ranges[stat_name]

    # Handle 0 values specially based on whether lower is better
    if value == 0 or value == 0.0:
        if lower_is_better:
            # For lower-is-better stats, 0 is the best (darkest red)
            return "background-color: rgb(220, 53, 69); color: white; font-weight: bold;"
        else:
            # For higher-is-better stats, 0 is the worst (darkest blue)
            return "background-color: rgb(0, 123, 255); color: white; font-weight: bold;"

    # Normalize the value
    normalized = (value - min_val) / (max_val - min_val) if max_val > min_val else 0.5
    normalized = max(0, min(1, normalized))

    # For lower-is-better stats, invert
    if lower_is_better:
        normalized = 1 - normalized

    # Create gradient color
    if normalized < 0.5:
        # Blue to white gradient (bad to neutral)
        factor = normalized * 2
        r = int(0 + (248 - 0) * factor)
        g = int(123 + (249 - 123) * factor)
        b = int(255 + (250 - 255) * factor)
        text_color = "white" if normalized < 0.2 else "#333"
        font_weight = "bold" if normalized < 0.3 else "normal"
    else:
        # White to red gradient (neutral to good)
        factor = (normalized - 0.5) * 2
        r = int(248 + (220 - 248) * factor)
        g = int(249 + (53 - 249) * factor)
        b = int(250 + (69 - 250) * factor)
        text_color = "#333" if normalized < 0.7 else "white"
        font_weight = "normal" if normalized < 0.7 else "bold"

    return f"background-color: rgb({r}, {g}, {b}); color: {text_color}; font-weight: {font_weight};"


# Utility functions
def add_origin_lines(ax):
    ax.axhline(0, color="black", linestyle="-", linewidth=0.5)
    ax.axvline(0, color="black", linestyle="-", linewidth=0.5)


def add_strike_zone(ax):    
    ax.plot([-0.85, 0.85], [1.6, 1.6], color="b", linewidth=1)    
    ax.plot([-0.85, 0.85], [3.4, 3.4], color="b", linewidth=1)    
    ax.plot([-0.85, -0.85], [1.6, 3.4], color="b", linewidth=1)    
    ax.plot([0.85, 0.85], [1.6, 3.4], color="b", linewidth=1)


def confidence_ellipse(x, y, ax, edgecolor, n_std=0.5, facecolor="none", **kwargs):
    """Add confidence ellipse to plot"""
    if len(x) < 2 or len(y) < 2:
        return

    # Remove NaN values
    valid_mask = ~(np.isnan(x) | np.isnan(y))
    x_clean = x[valid_mask]
    y_clean = y[valid_mask]

    if len(x_clean) < 2 or len(y_clean) < 2:
        return

    try:
        cov = np.cov(x_clean, y_clean)
        mean = [np.mean(x_clean), np.mean(y_clean)]

        if cov.ndim == 0:
            return

        eigvals, eigvecs = np.linalg.eigh(cov)
        order = eigvals.argsort()[::-1]
        eigvals, eigvecs = eigvals[order], eigvecs[:, order]

        if np.any(eigvals <= 0):
            return

        angle = np.degrees(np.arctan2(eigvecs[1, 0], eigvecs[0, 0]))
        width, height = 2 * n_std * np.sqrt(eigvals)

        ellipse = Ellipse(xy=mean, width=width, height=height, angle=angle,
                          edgecolor=edgecolor, facecolor=facecolor, **kwargs)
        ax.add_patch(ellipse)

    except Exception as e:
        print(f"Ellipse calculation failed: {e}")
        return


def simple_kde(data, x_range, bandwidth=None):
    """Simple KDE implementation using numpy"""
    if len(data) < 2:
        return np.zeros_like(x_range)

    if bandwidth is None:
        bandwidth = len(data) ** (-1.0 / 5.0) * np.std(data)

    bandwidth = max(bandwidth, 0.1)

    density = np.zeros_like(x_range)
    for point in data:
        density += np.exp(-0.5 * ((x_range - point) / bandwidth) ** 2)

    density = density / (len(data) * bandwidth * np.sqrt(2 * np.pi))
    return density

KSU_CSS = """
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;600;700;800&family=Barlow:wght@300;400;500;600&display=swap');

/* ── Root tokens ─────────────────────────────────────────── */
:root {
  --ksu-gold:    #FDBB30;
  --ksu-gold-dk: #D99A00;
  --ksu-dark:    #1A1A1A;
  --ksu-mid:     #242424;
  --ksu-panel:   #2C2C2C;
  --ksu-border:  #3A3A3A;
  --ksu-text:    #E8E8E8;
  --ksu-muted:   #999999;
  --ksu-accent:  #FDBB30;
  --radius:      6px;
  --shadow:      0 2px 12px rgba(0,0,0,0.4);
}

/* ── Page & body ─────────────────────────────────────────── */
body, .bslib-page-sidebar {
  background: var(--ksu-dark) !important;
  color: var(--ksu-text) !important;
  font-family: 'Barlow', sans-serif !important;
}

/* ── Sidebar ─────────────────────────────────────────────── */
.bslib-sidebar-layout > .sidebar {
  background: var(--ksu-mid) !important;
  border-right: 1px solid var(--ksu-border) !important;
  padding: 1rem 1rem 2rem !important;
}

/* Sidebar labels */
.bslib-sidebar-layout .form-label,
.bslib-sidebar-layout label,
.bslib-sidebar-layout .control-label {
  color: var(--ksu-muted) !important;
  font-size: 0.72rem !important;
  font-weight: 600 !important;
  text-transform: uppercase !important;
  letter-spacing: 0.06em !important;
  margin-bottom: 4px !important;
}

/* Sidebar inputs */
.bslib-sidebar-layout select,
.bslib-sidebar-layout input[type="number"],
.bslib-sidebar-layout input[type="text"],
.bslib-sidebar-layout input[type="date"],
.bslib-sidebar-layout .selectize-input {
  background: var(--ksu-panel) !important;
  border: 1px solid var(--ksu-border) !important;
  color: var(--ksu-text) !important;
  border-radius: var(--radius) !important;
  font-size: 0.85rem !important;
  padding: 6px 10px !important;
}

.bslib-sidebar-layout .selectize-dropdown {
  background: var(--ksu-panel) !important;
  border: 1px solid var(--ksu-border) !important;
  color: var(--ksu-text) !important;
}

.bslib-sidebar-layout .selectize-dropdown .option:hover,
.bslib-sidebar-layout .selectize-dropdown .option.active {
  background: var(--ksu-gold) !important;
  color: var(--ksu-dark) !important;
}

/* Switch */
.bslib-sidebar-layout .form-check-input:checked {
  background-color: var(--ksu-gold) !important;
  border-color: var(--ksu-gold) !important;
}

/* Radio buttons */
.bslib-sidebar-layout .form-check-label {
  color: var(--ksu-text) !important;
  font-size: 0.82rem !important;
  text-transform: none !important;
  letter-spacing: 0 !important;
  font-weight: 400 !important;
}

/* Sidebar divider section */
.sidebar-leaderboard-section {
  border-top: 1px solid var(--ksu-border);
  margin-top: 18px;
  padding-top: 14px;
}

.sidebar-leaderboard-section h4 {
  color: var(--ksu-gold) !important;
  font-family: 'Barlow Condensed', sans-serif !important;
  font-size: 0.8rem !important;
  font-weight: 700 !important;
  text-transform: uppercase !important;
  letter-spacing: 0.1em !important;
  margin-bottom: 10px !important;
}

/* ── Header / branding ───────────────────────────────────── */
.nest-header {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 10px 0 14px;
  border-bottom: 2px solid var(--ksu-gold);
  margin-bottom: 18px;
}

.nest-header .nest-title {
  font-family: 'Barlow Condensed', sans-serif;
  font-size: 2.1rem;
  font-weight: 800;
  color: var(--ksu-gold);
  letter-spacing: 0.04em;
  text-transform: uppercase;
  line-height: 1;
}

.nest-header .nest-subtitle {
  font-size: 0.75rem;
  color: var(--ksu-muted);
  text-transform: uppercase;
  letter-spacing: 0.12em;
  margin-top: 2px;
}

.nest-actions {
  margin-left: auto;
  display: flex;
  gap: 8px;
  align-items: center;
}

/* ── Buttons ─────────────────────────────────────────────── */
.btn-primary, .btn-default, .download-btn, button.btn {
  background: var(--ksu-gold) !important;
  color: var(--ksu-dark) !important;
  border: none !important;
  font-family: 'Barlow Condensed', sans-serif !important;
  font-weight: 700 !important;
  font-size: 0.8rem !important;
  letter-spacing: 0.05em !important;
  text-transform: uppercase !important;
  border-radius: var(--radius) !important;
  padding: 7px 16px !important;
  transition: background 0.15s, transform 0.1s !important;
}

.btn-primary:hover, .btn-default:hover, button.btn:hover {
  background: var(--ksu-gold-dk) !important;
  transform: translateY(-1px);
}

/* ── Nav tabs ─────────────────────────────────────────────── */
.nav-tabs {
  border-bottom: 2px solid var(--ksu-border) !important;
  gap: 2px;
}

.nav-tabs .nav-link {
  font-family: 'Barlow Condensed', sans-serif !important;
  font-size: 0.85rem !important;
  font-weight: 700 !important;
  text-transform: uppercase !important;
  letter-spacing: 0.06em !important;
  color: var(--ksu-muted) !important;
  background: transparent !important;
  border: none !important;
  border-bottom: 3px solid transparent !important;
  padding: 8px 18px !important;
  border-radius: 0 !important;
  transition: color 0.15s, border-color 0.15s !important;
}

.nav-tabs .nav-link:hover {
  color: var(--ksu-text) !important;
  border-bottom-color: var(--ksu-border) !important;
  background: transparent !important;
}

.nav-tabs .nav-link.active {
  color: var(--ksu-gold) !important;
  background: transparent !important;
  border-bottom: 3px solid var(--ksu-gold) !important;
}

/* ── Section cards ───────────────────────────────────────── */
.section-card {
  background: var(--ksu-mid) !important;
  border: 1px solid var(--ksu-border) !important;
  border-radius: var(--radius) !important;
  padding: 16px 18px !important;
  margin-bottom: 16px !important;
  box-shadow: var(--shadow) !important;
}

.section-card-title {
  font-family: 'Barlow Condensed', sans-serif !important;
  font-size: 0.78rem !important;
  font-weight: 700 !important;
  text-transform: uppercase !important;
  letter-spacing: 0.1em !important;
  color: var(--ksu-gold) !important;
  margin-bottom: 12px !important;
  padding-bottom: 8px !important;
  border-bottom: 1px solid var(--ksu-border) !important;
  display: flex !important;
  align-items: center !important;
  gap: 8px !important;
}

.section-card-title::before {
  content: '';
  display: inline-block;
  width: 3px;
  height: 14px;
  background: var(--ksu-gold);
  border-radius: 2px;
}

/* ── Tables ──────────────────────────────────────────────── */
table {
  background: var(--ksu-panel) !important;
  border-collapse: collapse !important;
}

th {
  background: #333 !important;
  color: var(--ksu-gold) !important;
  font-family: 'Barlow Condensed', sans-serif !important;
  font-size: 0.75rem !important;
  font-weight: 700 !important;
  text-transform: uppercase !important;
  letter-spacing: 0.06em !important;
  border: 1px solid var(--ksu-border) !important;
  padding: 9px 10px !important;
}

th:hover {
  background: #3c3c3c !important;
}

td {
  border: 1px solid var(--ksu-border) !important;
  color: var(--ksu-text) !important;
  font-size: 0.84rem !important;
}

tr:hover td {
  filter: brightness(1.08);
}

/* ── Plots ───────────────────────────────────────────────── */
.plot-container img {
  border-radius: var(--radius) !important;
  box-shadow: var(--shadow) !important;
  max-width: 100% !important;
}

/* ── Main content area ───────────────────────────────────── */
.bslib-sidebar-layout > .main {
  background: var(--ksu-dark) !important;
  padding: 16px 20px !important;
}

/* ── Scrollbar ───────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--ksu-dark); }
::-webkit-scrollbar-thumb { background: var(--ksu-border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--ksu-muted); }

/* ── Print ───────────────────────────────────────────────── */
@media print {
  .no-print { display: none !important; }
  body { background: white !important; color: black !important; }
}
</style>
"""

app_ui = ui.page_sidebar(
    ui.sidebar(
        # Logo inside sidebar at top
        ui.div(
            ui.img(
                src="https://upload.wikimedia.org/wikipedia/commons/thumb/6/63/Kennesaw_State_Owls_logo.svg/1200px-Kennesaw_State_Owls_logo.svg.png",
                style="height: 54px; display: block; margin: 0 auto 16px;"),
            style="text-align:center;"
        ),
        ui.input_switch("view_mode", "Team View", value=False),
        ui.panel_conditional(
            "!input.view_mode",
            ui.input_select("pitcher_id", "Select Pitcher",
                            {"": "— choose a pitcher —", **{p: p for p in all_pitchers}})
        ),
        ui.input_date_range("date_range", "Select Date Range",
                            start=min_date, end=max_date, min=min_date, max=max_date),
        ui.input_selectize("batter_hand_id", "Select Batter Hand",
                           unique_batter_sides, selected=unique_batter_sides, multiple=True),
        ui.input_radio_buttons("movement_color_by", "Color Movement Plot By:",
                               {"pitch_type": "Pitch Type", "arm_angle": "Arm Angle Type"},
                               selected="pitch_type"),
        ui.div(
            ui.div("Leaderboard Controls", class_="sidebar-leaderboard-section", style="color:#FDBB30;font-family:'Barlow Condensed',sans-serif;font-size:0.78rem;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:10px;"),
            ui.input_select("leaderboard_pitch_type", "Filter by Pitch Type:",
                            {"TOTAL": "All Pitches (TOTAL)", **{pt: pt for pt in all_pitch_types if pt != "TOTAL"}},
                            selected="TOTAL"),
            ui.input_selectize("leaderboard_pitch_types_multi", "Include Pitch Types:",
                               all_pitch_types, selected=all_pitch_types, multiple=True),
            ui.input_numeric("min_pitches", "Minimum Pitch Count:", value=50, min=1, max=1000),
            class_="sidebar-leaderboard-section"
        ),
        width=270
    ),

    # Inject CSS + header
    ui.tags.head(ui.HTML(KSU_CSS)),

    ui.div(
        ui.div(
            ui.img(
                src="https://upload.wikimedia.org/wikipedia/commons/thumb/6/63/Kennesaw_State_Owls_logo.svg/1200px-Kennesaw_State_Owls_logo.svg.png",
                style="height: 52px; flex-shrink:0;"),
            ui.div(
                ui.div("The Nest", class_="nest-title"),
                ui.div("KSU Baseball · Pitching Analytics", class_="nest-subtitle"),
            ),
            ui.div(
                ui.download_button("download_report", "↓ Report", class_="no-print"),
                ui.input_action_button("print_button", "⎙ Print", class_="no-print"),
                ui.tags.script("$(document).on('click', '#print_button', function() { window.print(); });"),
                class_="nest-actions"
            ),
            class_="nest-header"
        ),
    ),

    ui.navset_tab(
        ui.nav_panel("Everything",
            ui.div(
                ui.div("Summary Stats", class_="section-card-title"),
                ui.output_ui("everything_summary_stats_table"),
                class_="section-card"
            ),
            ui.div(
                ui.div("Pitch Metrics", class_="section-card-title"),
                ui.output_ui("everything_pitch_metrics_table"),
                class_="section-card"
            ),
            ui.div(
                ui.div("Pitch Stats", class_="section-card-title"),
                ui.output_ui("everything_pitch_stats_table"),
                class_="section-card"
            ),
            ui.row(
                ui.column(6, ui.div(ui.output_ui("everything_movement_plot"), class_="section-card")),
                ui.column(6, ui.div(ui.output_ui("everything_release_plot"), class_="section-card")),
            ),
            ui.row(
                ui.column(6, ui.div(ui.output_ui("everything_velocity_plot"), class_="section-card")),
                ui.column(6, ui.div(ui.output_ui("everything_location_plot"), class_="section-card")),
            ),
            ui.row(
                ui.column(6, ui.div(ui.output_ui("everything_strike_swinging_plot"), class_="section-card")),
                ui.column(6, ui.div(ui.output_ui("everything_chase_plot"), class_="section-card")),
            ),
            ui.row(
                ui.column(6, ui.div(ui.output_ui("everything_called_strike_plot"), class_="section-card")),
                ui.column(6, ui.div(ui.output_ui("everything_called_ball_plot"), class_="section-card")),
            ),
            ui.row(
                ui.column(6, ui.div(ui.output_ui("everything_arm_angle_plot"), class_="section-card")),
                ui.column(6, ui.div(
                    ui.div("Pitch Usage by Batter Hand", class_="section-card-title"),
                    ui.output_ui("everything_usage_by_hand_plot"),
                    class_="section-card"
                )),
            ),
        ),

        ui.nav_panel("Pitch Data",
            ui.div(
                ui.div("Pitch Metrics", class_="section-card-title"),
                ui.output_ui("data_pitch_metrics_table"),
                class_="section-card"
            ),
            ui.div(
                ui.div("Pitch Stats", class_="section-card-title"),
                ui.output_ui("data_pitch_stats_table"),
                class_="section-card"
            ),
            ui.row(
                ui.column(6, ui.div(ui.output_ui("data_movement_plot"), class_="section-card")),
                ui.column(6, ui.div(ui.output_ui("data_release_plot"), class_="section-card")),
            ),
        ),

        ui.nav_panel("Plots",
            ui.row(
                ui.column(6, ui.div(ui.output_ui("plots_velocity_plot"), class_="section-card")),
                ui.column(6, ui.div(ui.output_ui("plots_location_plot"), class_="section-card")),
            ),
            ui.row(
                ui.column(6, ui.div(ui.output_ui("plots_strike_swinging_plot"), class_="section-card")),
                ui.column(6, ui.div(ui.output_ui("plots_chase_plot"), class_="section-card")),
            ),
            ui.row(
                ui.column(6, ui.div(ui.output_ui("plots_called_strike_plot"), class_="section-card")),
                ui.column(6, ui.div(ui.output_ui("plots_called_ball_plot"), class_="section-card")),
            ),
            ui.row(
                ui.column(6, ui.div(
                    ui.div("Pitch Usage by Batter Hand", class_="section-card-title"),
                    ui.output_ui("plots_usage_by_hand_plot"),
                    class_="section-card"
                )),
                ui.column(6),
            ),
        ),

        ui.nav_panel("Tunneling",
            ui.div(
                ui.div("Release Angle Tunneling Analysis", class_="section-card-title"),
                ui.p("Analysis of pitch release angles to evaluate tunneling effectiveness at release point.",
                     style="color:var(--ksu-muted,#999);font-size:0.82rem;margin-bottom:12px;"),
                ui.output_ui("tunneling_release_angles_plot"),
                class_="section-card"
            ),
            ui.div(
                ui.div("Tunneling Metrics", class_="section-card-title"),
                ui.output_ui("tunneling_metrics_table"),
                class_="section-card"
            ),
        ),

        ui.nav_panel("Leaderboard",
            ui.div(
                ui.div("Pitch Metrics Leaderboard", class_="section-card-title"),
                ui.output_ui("leaderboard_metrics_table"),
                class_="section-card"
            ),
            ui.div(
                ui.div("Pitch Stats Leaderboard", class_="section-card-title"),
                ui.output_ui("leaderboard_stats_table"),
                class_="section-card"
            ),
        ),

        id="main_tabs"
    ),
)


# Server
def server(input, output, session):
    @reactive.Calc
    def filtered_data():
        view_mode = input.view_mode()
        date_range = input.date_range()
        batter_hands = input.batter_hand_id()

        # Start with KEN_OWL team data
        if "PitcherTeam" in df.columns:
            data = df[df["PitcherTeam"] == "KEN_OWL"].copy()
        else:
            data = df.copy()

        # If individual view, filter by selected pitcher
        if not view_mode:
            pitcher = input.pitcher_id()
            if not pitcher:
                return pd.DataFrame()
            data = data[data["Pitcher"] == pitcher].copy()
        if date_range and "Date" in data.columns:
            start_date = pd.to_datetime(date_range[0])
            end_date = pd.to_datetime(date_range[1])
            data = data[(data["Date"] >= start_date) & (data["Date"] <= end_date)]
        if batter_hands and "BatterSide" in data.columns:
            data = data[data["BatterSide"].isin(batter_hands)]
        return data

    @reactive.Calc
    def leaderboard_data():
        # First filter for KEN_OWL pitchers
        data = df[df["PitcherTeam"] == "KEN_OWL"].copy()

        # Then apply date range filter if specified
        selected_dates = input.date_range()
        if selected_dates and "Date" in data.columns:
            start_date = pd.to_datetime(selected_dates[0])
            end_date = pd.to_datetime(selected_dates[1])
            data = data[(data["Date"] >= start_date) & (data["Date"] <= end_date)]

        # Apply batter hand filter if specified
        batter_hands = input.batter_hand_id()
        if batter_hands and "BatterSide" in data.columns:
            data = data[data["BatterSide"].isin(batter_hands)]

        return data

    def create_pitch_metrics_table():
        data = filtered_data()
        view_mode = input.view_mode()

        if view_mode:
            display_name = "KEN_OWL Team"
        else:
            pitcher = input.pitcher_id()
            if not pitcher:
                return ui.div("No data available")
            display_name = pitcher
            pitcher = display_name

        if data.empty:
            return ui.div("No data available")

        required_cols = ["PitchType", "RelSpeed"]
        missing_cols = [col for col in required_cols if col not in data.columns]
        if missing_cols:
            return ui.div(f"Required columns missing: {missing_cols}")

        # Convert numeric columns
        numeric_cols = ["RelSpeed", "InducedVertBreak", "HorzBreak", "SpinRate", "RelHeight", "RelSide", "Extension",
                        "VertApprAngle", "HorzApprAngle"]
        if "Tilt" in data.columns:
            numeric_cols.append("Tilt")
        if "arm_angle" in data.columns:
            numeric_cols.append("arm_angle")

        for col in numeric_cols:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors="coerce")

        grouped = data.groupby("PitchType")

        # Build aggregation dictionary
        agg_dict = {
            "AvgVelo": ("RelSpeed", "mean"),
            "InducedVertBreak": ("InducedVertBreak", "mean"),
            "HorzBreak": ("HorzBreak", "mean"),
            "SpinRate": ("SpinRate", "mean"),
            "RelHeight": ("RelHeight", "mean"),
            "RelSide": ("RelSide", "mean"),
            "Extension": ("Extension", "mean"),
            "VertApprAngle": ("VertApprAngle", "mean"),
            "HorzApprAngle": ("HorzApprAngle", "mean")
        }

        # Add Tilt only if it exists and has valid data
        if "Tilt" in data.columns and data["Tilt"].notna().sum() > 0:
            agg_dict["Tilt"] = ("Tilt", "mean")

        metrics = grouped.agg(**agg_dict).round(1)

        if "arm_angle" in data.columns:
            metrics["ArmAngle"] = (90 - grouped["arm_angle"].mean()).round(1)

        metrics["MaxVelo"] = grouped["RelSpeed"].max().round(1)
        usage_percentage = data["PitchType"].value_counts(normalize=True) * 100
        metrics["Usage%"] = usage_percentage.reindex(metrics.index, fill_value=0.0).round(1)
        pitch_counts = data["PitchType"].value_counts()
        metrics["Count"] = pitch_counts.reindex(metrics.index, fill_value=0)

        metrics = metrics.reset_index()
        metrics = metrics.rename(columns={
            "InducedVertBreak": "IVB", "HorzBreak": "HB", "VertApprAngle": "VAA",
            "HorzApprAngle": "HAA", "AvgVelo": "Vel", "Extension": "Extension"
        })

        # Build column order dynamically
        column_order = ["PitchType", "Count", "Usage%", "Vel", "MaxVelo", "IVB", "HB", "SpinRate"]

        # Add Tilt if it exists in the metrics
        if "Tilt" in metrics.columns:
            column_order.append("Tilt")

        column_order.extend(["RelHeight", "RelSide", "VAA", "HAA", "Extension"])

        if "ArmAngle" in metrics.columns:
            column_order.insert(-3, "ArmAngle")

        metrics = metrics[column_order].fillna(0)

        # Add TOTAL row
        total_row = {'PitchType': 'TOTAL', 'Count': metrics['Count'].sum(), 'Usage%': 100.0}

        # Calculate weighted averages for all numeric columns
        base_cols = ['Vel', 'MaxVelo', 'IVB', 'HB', 'SpinRate', 'RelHeight', 'RelSide', 'VAA', 'HAA', 'Extension']
        if "Tilt" in metrics.columns:
            base_cols.insert(5, 'Tilt')  # Insert after SpinRate

        for col in base_cols:
            if col in metrics.columns and col != 'MaxVelo':
                weighted_sum = (metrics[col] * metrics['Count']).sum()
                total_count = metrics['Count'].sum()
                total_row[col] = round(weighted_sum / total_count, 1) if total_count > 0 else 0.0
            elif col == 'MaxVelo':
                total_row[col] = metrics['MaxVelo'].max()

        if "ArmAngle" in metrics.columns and "arm_angle" in data.columns:
            weighted_arm_angles = (data.groupby('PitchType')['arm_angle'].mean() * metrics['Count']).sum()
            total_count = metrics['Count'].sum()
            total_row['ArmAngle'] = round(90 - (weighted_arm_angles / total_count), 1) if total_count > 0 else 0.0
        total_df = pd.DataFrame([total_row])
        metrics = pd.concat([metrics, total_df], ignore_index=True)

        # Create HTML table
        table_id = "metrics_table_" + str(hash(display_name) % 10000)
        html = f'<table id="{table_id}" style="border-collapse: collapse; width: 100%; font-size: 14px;">'
        html += '<thead><tr>'
        for col in metrics.columns:
            html += f'<th style="border: 1px solid #ddd; padding: 8px; background-color: #f8f9fa;">{col}</th>'
        html += '</tr></thead><tbody>'

        for _, row in metrics.iterrows():
            html += '<tr>'
            for col, value in row.items():
                if col == 'PitchType':
                    if value == 'TOTAL':
                        html += f'<td style="border: 1px solid #ddd; padding: 6px; background-color: #333333; color: white; font-weight: bold; text-align: center; border-radius: 4px;">{value}</td>'
                    else:
                        color = pitch_colors_dict.get(value, "#9C8975")
                        html += f'<td style="border: 1px solid #ddd; padding: 6px; background-color: {color}; color: white; font-weight: bold; text-align: center; border-radius: 4px;">{value}</td>'
                elif col in ['Vel', 'Extension'] and value != 0 and row['PitchType'] != 'TOTAL':
                    # Color performance metrics
                    style = get_performance_color(value, row['PitchType'], col)
                    formatted_value = f"{value:.1f}" if isinstance(value, (int, float)) and value != int(
                        value) else str(value)
                    html += f'<td style="border: 1px solid #ddd; padding: 8px; text-align: center; {style}">{formatted_value}</td>'
                else:
                    formatted_value = f"{value:.1f}" if isinstance(value, (int, float)) and value != int(
                        value) else str(value)
                    if row['PitchType'] == 'TOTAL':
                        html += f'<td style="border: 1px solid #ddd; padding: 8px; text-align: center; font-weight: bold; background-color: #f0f0f0;">{formatted_value}</td>'
                    else:
                        html += f'<td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{formatted_value}</td>'
            html += '</tr>'

        html += '</tbody></table>'
        html += SORTABLE_TABLE_JS
        html += f'<script>setTimeout(() => makeSortable("{table_id}"), 100);</script>'
        return ui.HTML(html)

    def create_summary_stats_table():
        """Create a summary table with overall pitcher stats (K%, BB%, FIP, etc.)"""
        data = filtered_data()
        view_mode = input.view_mode()

        if view_mode:
            display_name = "KEN_OWL Team"
        else:
            pitcher = input.pitcher_id()
            if not pitcher:
                return ui.div("No data available")
            display_name = pitcher

        if data.empty:
            return ui.div("No data available")

        # Calculate overall stats (not by pitch type)
        summary = {}

        # Count unique plate appearances
        if all(col in data.columns for col in ["GameID", "Inning", "Top/Bottom", "PAofInning"]):
            unique_pas = data.groupby(["GameID", "Inning", "Top/Bottom", "PAofInning"]).ngroups
            if view_mode:
                print(f"\nUnique PAs (with Top/Bottom): {unique_pas}")
        elif all(col in data.columns for col in ["CustomGameID", "Inning", "Top/Bottom", "PAofInning"]):
            unique_pas = data.groupby(["CustomGameID", "Inning", "Top/Bottom", "PAofInning"]).ngroups
        elif all(col in data.columns for col in ["Date", "Inning", "Top/Bottom", "PAofInning"]):
            unique_pas = data.groupby(["Date", "Inning", "Top/Bottom", "PAofInning"]).ngroups
        elif all(col in data.columns for col in ["GameID", "Inning", "PAofInning"]):
            unique_pas = data.groupby(["GameID", "Inning", "PAofInning"]).ngroups
        elif "KorBB" in data.columns:
            unique_pas = len(data[data["KorBB"] != "Undefined"])
        else:
            unique_pas = len(data)

        # K%
        if "KorBB" in data.columns:
            k_count = len(data[data["KorBB"] == "Strikeout"])
            summary["K%"] = round((k_count / unique_pas * 100), 1) if unique_pas > 0 else 0.0
        else:
            summary["K%"] = 0.0

        # BB%
        if "KorBB" in data.columns:
            bb_count = len(data[data["KorBB"] == "Walk"])
            summary["BB%"] = round((bb_count / unique_pas * 100), 1) if unique_pas > 0 else 0.0
        else:
            summary["BB%"] = 0.0

      # FIP - Fielding Independent Pitching: ((13*HR)+(3*(BB+HBP))-(2*K))/IP + 3.18
        if "KorBB" in data.columns:
            # --- PA-ending rows ---
            pa_end = data[
                (data["KorBB"].notna() & (data["KorBB"] != "Undefined")) |
                (data["PitchCall"] == "InPlay") |
                (data["PitchCall"] == "HitByPitch")
            ]

            # --- counts (PA-ending only) ---
            hr_count = 0
            if "PlayResult" in pa_end.columns:
                hr_count = len(pa_end[pa_end["PlayResult"] == "HomeRun"])

            k_count  = len(pa_end[pa_end["KorBB"] == "Strikeout"])
            bb_count = len(pa_end[pa_end["KorBB"] == "Walk"])

            # HBP may live in PitchCall or KorBB depending on source
            hbp_count = 0
            if "PitchCall" in pa_end.columns:
                hbp_count += len(pa_end[pa_end["PitchCall"] == "HitByPitch"])
            if "KorBB" in pa_end.columns:
                hbp_count += len(pa_end[pa_end["KorBB"] == "HitByPitch"])

            # --- IP from OutsOnPlay + Strikeouts ---
            if "OutsOnPlay" in pa_end.columns:
                outs_from_play = pa_end["OutsOnPlay"].fillna(0).sum()
                total_outs = outs_from_play + k_count
                ip = total_outs / 3.0
                if view_mode:
                    print(f"\nFIP Debug (fixed):")
                    print(f"  OutsOnPlay: {outs_from_play}, Strikeouts: {k_count}, Total Outs: {total_outs}, IP: {ip:.2f}")
                    print(f"  HR: {hr_count}, BB: {bb_count}, HBP: {hbp_count}, K: {k_count}")
            else:
                ip = unique_pas / 3.33
                if view_mode:
                    print(f"\nFIP Debug (estimated IP):")
                    print(f"  PAs: {unique_pas}, IP: {ip:.2f}")
                    print(f"  HR: {hr_count}, BB: {bb_count}, HBP: {hbp_count}, K: {k_count}")

            if ip > 0:
                fip_constant = 3.18
                fip_numerator = (13 * hr_count) + (3 * (bb_count + hbp_count)) - (2 * k_count)
                summary["FIP"] = round((fip_numerator / ip) + fip_constant, 2)
                if view_mode:
                    print(f"  Numerator: {fip_numerator}, FIP: {summary['FIP']}")
            else:
                summary["FIP"] = 0.0
        else:
            summary["FIP"] = 0.0

        # Barrel% - proper barrel definition
        in_play = data[data["PitchCall"] == "InPlay"]
        if all(col in in_play.columns for col in ["ExitSpeed", "Angle"]) and not in_play.empty:
            # Check for valid exit speed and angle data
            valid_contact = in_play[(in_play["ExitSpeed"].notna()) & (in_play["Angle"].notna())]

            if len(valid_contact) > 0:
                barrels = valid_contact[
                        (valid_contact["ExitSpeed"] >= 95) &
                        (valid_contact["Angle"] >= 10) &
                        (valid_contact["Angle"] <= 35)
                 ]
                summary["Barrel%"] = round((len(barrels) / len(valid_contact) * 100), 1)

                if view_mode:
                    print(f"\nBarrel% Debug:")
                    print(f"  Balls in play: {len(in_play)}")
                    print(f"  Valid contact (with EV & LA): {len(valid_contact)}")
                    print(f"  Barrels: {len(barrels)}")
                    print(f"  Barrel%: {summary['Barrel%']}")
            else:
                summary["Barrel%"] = 0.0
        else:
            summary["Barrel%"] = 0.0

        # HardHit% - Exit velo 95+ mph
        if "ExitSpeed" in in_play.columns and not in_play.empty:
            valid_contact = in_play[in_play["ExitSpeed"].notna()]
            if len(valid_contact) > 0:
                hard_hits = valid_contact[valid_contact["ExitSpeed"] >= 95]
                summary["HardHit%"] = round((len(hard_hits) / len(valid_contact) * 100), 1)

                if view_mode:
                    print(f"\nHardHit% Debug:")
                    print(f"  Valid contact: {len(valid_contact)}")
                    print(f"  Hard hits (95+ mph): {len(hard_hits)}")
                    print(f"  HardHit%: {summary['HardHit%']}")
            else:
                summary["HardHit%"] = 0.0
        else:
            summary["HardHit%"] = 0.0

        # BAA (Batting Average Against)
        if "PlayResult" in data.columns and "KorBB" in data.columns:
            walks = data[data["KorBB"] == "Walk"]
            hbp = data[data["KorBB"] == "HitByPitch"]
            sac = data[data["PlayResult"].str.contains("Sacrifice", case=False, na=False)]

            at_bats = unique_pas - len(walks) - len(hbp) - len(sac)
            hits = data[data["PlayResult"].isin(["Single", "Double", "Triple", "HomeRun"])]

            summary["BAA"] = round((len(hits) / at_bats), 3) if at_bats > 0 else 0.0
        else:
            summary["BAA"] = 0.0

        # wOBA (weighted on-base average)
        if "PlayResult" in data.columns and "KorBB" in data.columns:
            woba_values = {
                "Walk": 0.69,
                "HitByPitch": 0.72,
                "Single": 0.88,
                "Double": 1.24,
                "Triple": 1.56,
                "HomeRun": 2.08
            }

            total_woba = 0
            woba_events = 0

            walks = data[data["KorBB"] == "Walk"]
            total_woba += len(walks) * woba_values["Walk"]
            woba_events += len(walks)

            hbp = data[data["KorBB"] == "HitByPitch"]
            total_woba += len(hbp) * woba_values["HitByPitch"]
            woba_events += len(hbp)

            for hit_type in ["Single", "Double", "Triple", "HomeRun"]:
                hits = data[data["PlayResult"] == hit_type]
                total_woba += len(hits) * woba_values[hit_type]
                woba_events += len(hits)

            outs = data[data["PlayResult"] == "Out"]
            strikeouts = data[data["KorBB"] == "Strikeout"]
            woba_events += len(outs) + len(strikeouts)

            summary["wOBA"] = round((total_woba / woba_events), 3) if woba_events > 0 else 0.0
        else:
            summary["wOBA"] = 0.0

        # Create HTML table
        table_id = "summary_stats_table_" + str(hash(display_name) % 10000)

        # Add header with context
        header_text = f"{display_name} Summary Stats"
        if view_mode:
            num_pitchers = data['Pitcher'].nunique() if 'Pitcher' in data.columns else 0
            header_text = f"KEN_OWL Team Summary Stats ({num_pitchers} Pitchers)"

        html = f'<div style="margin-bottom: 10px; font-weight: bold; font-size: 14px; color: #333;">{header_text}</div>'
        html += f'<table id="{table_id}" style="border-collapse: collapse; width: 100%; font-size: 14px;">'
        html += '<thead><tr>'
        for col in summary.keys():
            html += f'<th style="border: 1px solid #ddd; padding: 8px; background-color: #f8f9fa;">{col}</th>'
        html += '</tr></thead><tbody><tr>'

        for col, value in summary.items():
            if col in ['K%', 'BB%', 'FIP', 'Barrel%', 'HardHit%', 'BAA', 'wOBA'] and value != 0:
                # Apply color coding based on value ranges
                style = get_summary_stat_color(value, col)
                formatted_value = format_summary_stat(col, value)
                html += f'<td style="border: 1px solid #ddd; padding: 8px; text-align: center; {style}">{formatted_value}</td>'
            else:
                # Regular formatting for other columns
                formatted_value = format_summary_stat(col, value)
                html += f'<td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{formatted_value}</td>'

        html += '</tr></tbody></table>'
        html += SORTABLE_TABLE_JS
        html += f'<script>setTimeout(() => makeSortable("{table_id}"), 100);</script>'
        return ui.HTML(html)

    def create_pitch_stats_table():
        data = filtered_data()
        view_mode = input.view_mode()

        if view_mode:
            display_name = "KEN_OWL Team"
        else:
            pitcher = input.pitcher_id()
            if not pitcher:
                return ui.div("No data available")
            display_name = pitcher

        if data.empty:
            return ui.div("No data available")
        pitcher = display_name

        # ADD THIS DIAGNOSTIC CODE HERE
        if display_name == "Ty Bayer":
            print(f"\n{'=' * 50}")
            print(f"ANALYZING TY BAYER")
            print(f"{'=' * 50}")
            print(f"Total pitches: {len(data)}")

            if "PitchofPA" in data.columns:
                first_pitches = data[data["PitchofPA"] == 1]
                print(f"\nFirst pitches (PitchofPA==1): {len(first_pitches)}")
                print(f"\nBreakdown by PitchType:")
                print(first_pitches["PitchType"].value_counts())

                print(f"\nFirst pitch strikes:")
                first_strikes = first_pitches[first_pitches["PitchCall"].isin([
                    "StrikeCalled", "StrikeSwinging", "FoulBall", "FoulBallNotFieldable", "InPlay"
                ])]
                print(first_strikes["PitchType"].value_counts())

                print(f"\nTotal first pitches: {len(first_pitches)}")
                print(f"Total first pitch strikes: {len(first_strikes)}")
                print(f"Overall 1PK%: {(len(first_strikes) / len(first_pitches) * 100):.1f}%")

        # Continue with the rest of the function...
        required_cols = ["PitchType", "inZone", "PitchCall"]
        if not all(col in data.columns for col in required_cols):
            return ui.div("Required columns missing")

        grouped = data.groupby("PitchType")
        pitch_types = data["PitchType"].unique()
        stats = pd.DataFrame(index=pitch_types)

        # Calculate ExitVel and LaunchAng only from balls in play
        in_play_pitches = data[data["PitchCall"] == "InPlay"]

        if "ExitSpeed" in data.columns and not in_play_pitches.empty:
            in_play_grouped = in_play_pitches.groupby("PitchType")
            stats["ExitVel"] = in_play_grouped["ExitSpeed"].mean().reindex(stats.index, fill_value=0.0).round(1)
        else:
            stats["ExitVel"] = 0.0

        if "Angle" in data.columns and not in_play_pitches.empty:
            in_play_grouped = in_play_pitches.groupby("PitchType")
            stats["LaunchAng"] = in_play_grouped["Angle"].mean().reindex(stats.index, fill_value=0.0).round(1)
        else:
            stats["LaunchAng"] = 0.0

        # Calculate batted ball percentages
        if "Angle" in data.columns:
            in_play_data = data[data["PitchCall"] == "InPlay"].copy()
            if not in_play_data.empty:
                # Ground balls: < 10 degrees
                gb_data = in_play_data[in_play_data["Angle"] < 10]
                gb_counts = gb_data.groupby("PitchType").size()

                # Line drives: 10-25 degrees
                ld_data = in_play_data[(in_play_data["Angle"] >= 10) & (in_play_data["Angle"] <= 25)]
                ld_counts = ld_data.groupby("PitchType").size()

                # Fly balls: > 25 degrees
                fb_data = in_play_data[in_play_data["Angle"] > 25]
                fb_counts = fb_data.groupby("PitchType").size()

                # Home runs (if PlayResult column exists, otherwise use high angle + high exit velo)
                if "PlayResult" in data.columns:
                    hr_data = in_play_data[in_play_data["PlayResult"].str.contains("HomeRun", na=False)]
                elif "ExitSpeed" in data.columns:
                    hr_data = fb_data[(fb_data["Angle"] > 25) & (fb_data["ExitSpeed"] > 95)]
                else:
                    hr_data = fb_data[fb_data["Angle"] > 35]  # Very high angle as proxy
                hr_counts = hr_data.groupby("PitchType").size()

                # Total balls in play for each pitch type
                total_bip = in_play_data.groupby("PitchType").size()

                # Calculate percentages
                stats["GB%"] = (gb_counts / total_bip * 100).reindex(stats.index, fill_value=0.0).round(1)
                stats["LD%"] = (ld_counts / total_bip * 100).reindex(stats.index, fill_value=0.0).round(1)
                stats["FB%"] = (fb_counts / total_bip * 100).reindex(stats.index, fill_value=0.0).round(1)

                # HR/FB% - home runs as percentage of fly balls
                stats["HR/FB%"] = (hr_counts / fb_counts * 100).reindex(stats.index, fill_value=0.0).round(1)
            else:
                stats["GB%"] = 0.0
                stats["LD%"] = 0.0
                stats["FB%"] = 0.0
                stats["HR/FB%"] = 0.0
        else:
            stats["GB%"] = 0.0
            stats["LD%"] = 0.0
            stats["FB%"] = 0.0
            stats["HR/FB%"] = 0.0

        # Calculate percentage stats with corrected logic
        if "PitchofPA" in data.columns:
            first_pitches = data[data["PitchofPA"] == 1]
            if not first_pitches.empty:
                # Group by pitch type
                first_pitch_grouped = first_pitches.groupby("PitchType")

                # First pitch strikes include all strikes, fouls, and balls in play
                first_strikes = first_pitches[first_pitches["PitchCall"].isin([
                    "StrikeCalled", "StrikeSwinging", "FoulBall", "FoulBallNotFieldable", "InPlay"
                ])]

                # Group strikes by pitch type
                first_strikes_grouped = first_strikes.groupby("PitchType")

                # Calculate percentage for each pitch type
                total_first = first_pitch_grouped.size()
                strikes_first = first_strikes_grouped.size()
                first_pitch_pct = (strikes_first / total_first * 100).round(1)
                stats["1PK%"] = first_pitch_pct.reindex(stats.index, fill_value=0.0)

                # ADD DIAGNOSTIC CODE RIGHT HERE
                if display_name == "Ty Bayer":
                    print("\n=== 1PK% DIAGNOSTIC ===")
                    print(f"Pitcher: {display_name}")
                    print(f"\nTotal first pitches by pitch type:")
                    print(total_first)
                    print(f"\nFirst pitch strikes by pitch type:")
                    print(strikes_first)
                    print(f"\n1PK% by pitch type:")
                    print(first_pitch_pct)
                    print(f"\nFinal stats['1PK%']:")
                    print(stats["1PK%"])
            else:
                stats["1PK%"] = 0.0

            # 2of3% - Modified logic for base hits and outs in first 3 pitches
            if "CustomGameID" in data.columns or "Inning" in data.columns:
                # Try to identify at-bats properly
                groupby_cols = []
                if "CustomGameID" in data.columns:
                    groupby_cols.append("CustomGameID")
                if "Inning" in data.columns:
                    groupby_cols.append("Inning")
                if "PAofInning" in data.columns:
                    groupby_cols.append("PAofInning")
                elif "Batter" in data.columns:
                    groupby_cols.append("Batter")

                if groupby_cols:
                    # Get at-bats that have at least 2 pitches
                    at_bat_groups = data.groupby(groupby_cols)

                    two_of_three_counts = {}
                    total_ab_counts = {}

                    for ab_id, ab_data in at_bat_groups:
                        if len(ab_data) >= 2:  # At least 2 pitches in this at-bat
                            # Get first three pitches
                            first_three = ab_data[ab_data["PitchofPA"].isin([1, 2, 3])].sort_values("PitchofPA")

                            if len(first_three) >= 2:
                                counts_success = True

                                # Get pitch outcomes
                                for idx, pitch in first_three.iterrows():
                                    pitch_num = pitch["PitchofPA"]
                                    pitch_call = pitch["PitchCall"]

                                    # Determine balls and strikes up to this point
                                    pitches_so_far = first_three[first_three["PitchofPA"] <= pitch_num]
                                    balls = len(pitches_so_far[pitches_so_far["PitchCall"].isin(["BallCalled"])])
                                    strikes = len(pitches_so_far[pitches_so_far["PitchCall"].isin([
                                        "StrikeCalled", "StrikeSwinging", "FoulBall", "FoulBallNotFieldable"
                                    ])])

                                    # HBP never counts
                                    if pitch_call == "HitByPitch":
                                        counts_success = False
                                        break

                                    # Check for 2-0 count (never counts, regardless of outcome)
                                    if balls == 2 and strikes == 0:
                                        counts_success = False
                                        break

                                    # Check for 1-0 count with base hit (never counts)
                                    if balls == 1 and strikes == 0 and pitch_call == "InPlay":
                                        # Check if it's a hit (not an out)
                                        if "PlayResult" in ab_data.columns:
                                            play_result = pitch.get("PlayResult", "")
                                            if play_result and "Out" not in str(play_result):
                                                counts_success = False
                                                break
                                        else:
                                            # Without PlayResult, assume InPlay at 1-0 is a hit
                                            counts_success = False
                                            break

                                # Check if we achieved 2 strikes in first 3 pitches
                                first_three_strikes = first_three["PitchCall"].isin([
                                    "StrikeCalled", "StrikeSwinging", "FoulBall", "FoulBallNotFieldable", "InPlay"
                                ])

                                # Count for each pitch type in this at-bat
                                for pitch_type in first_three["PitchType"].unique():
                                    if pitch_type not in two_of_three_counts:
                                        two_of_three_counts[pitch_type] = 0
                                        total_ab_counts[pitch_type] = 0

                                    total_ab_counts[pitch_type] += 1

                                    # Success if 2+ strikes AND conditions are met
                                    if first_three_strikes.sum() >= 2 and counts_success:
                                        two_of_three_counts[pitch_type] += 1

                    # Calculate percentages
                    two_of_three_pct = {}
                    for pitch_type in total_ab_counts.keys():
                        if total_ab_counts[pitch_type] > 0:
                            two_of_three_pct[pitch_type] = (two_of_three_counts[pitch_type] / total_ab_counts[
                                pitch_type]) * 100
                        else:
                            two_of_three_pct[pitch_type] = 0.0

                    # Convert to Series and align with stats index
                    two_of_three_series = pd.Series(two_of_three_pct)
                    stats["2of3%"] = two_of_three_series.reindex(stats.index, fill_value=0.0).round(1)
                else:
                    stats["2of3%"] = 0.0
            else:
                stats["2of3%"] = 0.0
        else:
            stats["1PK%"] = 0.0
            stats["2of3%"] = 0.0

        # Strike% - all strikes including fouls and balls in play
        all_strikes = data[data["PitchCall"].isin([
            "StrikeCalled", "StrikeSwinging", "FoulBall", "FoulBallNotFieldable", "InPlay"
        ])]
        if not all_strikes.empty:
            strike_counts = all_strikes.groupby("PitchType").size()
            total_pitches = data.groupby("PitchType").size()
            strike_pct = (strike_counts / total_pitches * 100).round(1)
            stats["Strike%"] = strike_pct.reindex(stats.index, fill_value=0.0)
        else:
            stats["Strike%"] = 0.0

        # Zone% - percentage of pitches in the strike zone
        if "inZone" in data.columns:
            zone_pitches = data[data["inZone"] == 1]
            if not zone_pitches.empty:
                zone_counts = zone_pitches.groupby("PitchType").size()
                total_pitches = data.groupby("PitchType").size()
                zone_pct = (zone_counts / total_pitches * 100).round(1)
                stats["Zone%"] = zone_pct.reindex(stats.index, fill_value=0.0)
            else:
                stats["Zone%"] = 0.0
        else:
            stats["Zone%"] = 0.0

        # SwStr% - swinging strikes as percentage of all pitches
        sw_strikes = data[data["PitchCall"] == "StrikeSwinging"]
        if not sw_strikes.empty:
            swstr_counts = sw_strikes.groupby("PitchType").size()
            total_pitches = data.groupby("PitchType").size()
            swstr_pct = (swstr_counts / total_pitches * 100).round(1)
            stats["SwStr%"] = swstr_pct.reindex(stats.index, fill_value=0.0)
        else:
            stats["SwStr%"] = 0.0

        # Miss% - whiffs as percentage of all swings
        swings = data[data["PitchCall"].isin(["StrikeSwinging", "FoulBall", "FoulBallNotFieldable", "InPlay"])]
        whiffs = data[data["PitchCall"] == "StrikeSwinging"]
        if not swings.empty:
            swing_counts = swings.groupby("PitchType").size()
            whiff_counts = whiffs.groupby("PitchType").size()
            whiff_pct = (whiff_counts / swing_counts * 100).round(1)
            stats["Miss%"] = whiff_pct.reindex(stats.index, fill_value=0.0)
        else:
            stats["Miss%"] = 0.0

        # IZWhiff% - in-zone whiffs as percentage of in-zone swings
        inzone_swings = data[(data["inZone"] == 1) & (data["PitchCall"].isin([
            "StrikeSwinging", "FoulBall", "FoulBallNotFieldable", "InPlay"
        ]))]
        inzone_whiffs = data[(data["inZone"] == 1) & (data["PitchCall"] == "StrikeSwinging")]
        if not inzone_swings.empty:
            inzone_swing_counts = inzone_swings.groupby("PitchType").size()
            inzone_whiff_counts = inzone_whiffs.groupby("PitchType").size()
            iz_whiff_pct = (inzone_whiff_counts / inzone_swing_counts * 100).round(1)
            stats["IZWhiff%"] = iz_whiff_pct.reindex(stats.index, fill_value=0.0)
        else:
            stats["IZWhiff%"] = 0.0

        usage_percentage = data["PitchType"].value_counts(normalize=True) * 100
        stats["Usage%"] = usage_percentage.reindex(stats.index, fill_value=0.0).round(1)
        pitch_counts = data["PitchType"].value_counts()
        stats["Count"] = pitch_counts.reindex(stats.index, fill_value=0)

        stats = stats.reset_index()
        stats = stats.rename(columns={"index": "PitchType"})
        # Only include columns that actually exist in stats DataFrame
        column_order = ["PitchType", "Count", "Usage%"]

        # Add the new stats columns if they exist
        for col in ["K%", "BB%", "FIP", "Barrel%", "HardHit%", "BAA", "wOBA"]:
            if col in stats.columns:
                column_order.append(col)

        # Add the existing stats columns
        for col in ["1PK%", "2of3%", "Zone%", "Strike%", "SwStr%", "Miss%", "IZWhiff%",
                    "ExitVel", "LaunchAng", "GB%", "LD%", "FB%"]:
            if col in stats.columns:
                column_order.append(col)

        stats = stats[column_order].fillna(0)
        # Add TOTAL row
        total_row = {'PitchType': 'TOTAL', 'Count': stats['Count'].sum(), 'Usage%': 100.0}

        # Calculate 1PK% using actual first pitch counts, not weighted average
        if '1PK%' in stats.columns and 'PitchofPA' in data.columns:
            first_pitches_all = data[data["PitchofPA"] == 1]
            if len(first_pitches_all) > 0:
                first_strikes_all = first_pitches_all[first_pitches_all["PitchCall"].isin([
                    "StrikeCalled", "StrikeSwinging", "FoulBall", "FoulBallNotFieldable", "InPlay"
                ])]
                total_row['1PK%'] = round((len(first_strikes_all) / len(first_pitches_all) * 100), 1)
            else:
                total_row['1PK%'] = 0.0

        # Calculate weighted averages for other columns
        available_cols = ['2of3%', 'Zone%', 'Strike%', 'SwStr%', 'Miss%', 'IZWhiff%',
                          'ExitVel', 'LaunchAng', 'GB%', 'LD%', 'FB%']

        for col in available_cols:
            if col in stats.columns:
                weighted_sum = (stats[col] * stats['Count']).sum()
                total_count = stats['Count'].sum()
                total_row[col] = round(weighted_sum / total_count, 1) if total_count > 0 else 0.0
            else:
                total_row[col] = 0.0

        # ADD THIS RIGHT BEFORE creating total_df
        if display_name == "Ty Bayer":
            print("\n=== BEFORE TOTAL ROW ===")
            print("stats DataFrame (relevant columns):")
            print(stats[['PitchType', 'Count', '1PK%']])
            print(f"\nTotal row being added:")
            print(f"1PK% calculation: {total_row.get('1PK%', 'NOT SET')}")

        total_df = pd.DataFrame([total_row])
        stats = pd.concat([stats, total_df], ignore_index=True)

        # AND ADD THIS RIGHT AFTER
        if display_name == "Ty Bayer":
            print("\n=== AFTER TOTAL ROW ===")
            print("Final stats DataFrame:")
            print(stats[['PitchType', 'Count', 'Usage%', '1PK%']])

        # Create HTML table
        table_id = "stats_table_" + str(hash(display_name) % 10000)
        html = f'<table id="{table_id}" style="border-collapse: collapse; width: 100%; font-size: 14px;">'
        html += '<thead><tr>'
        for col in stats.columns:
            html += f'<th style="border: 1px solid #ddd; padding: 8px; background-color: #f8f9fa;">{col}</th>'
        html += '</tr></thead><tbody>'

        for _, row in stats.iterrows():
            html += '<tr>'
            for col, value in row.items():
                if col == 'PitchType':
                    if value == 'TOTAL':
                        html += f'<td style="border: 1px solid #ddd; padding: 6px; background-color: #333333; color: white; font-weight: bold; text-align: center; border-radius: 4px;">{value}</td>'
                    else:
                        color = pitch_colors_dict.get(value, "#9C8975")
                        html += f'<td style="border: 1px solid #ddd; padding: 6px; background-color: {color}; color: white; font-weight: bold; text-align: center; border-radius: 4px;">{value}</td>'
                elif col in ['Miss%', '1PK%', '2of3%','Zone%', 'Strike%', 'SwStr%', 'IZWhiff%', 'ExitVel', 'LaunchAng', 'GB%',
                             'LD%', 'FB%'] and value != 0:
                    style = get_performance_color(value, row['PitchType'], col)
                    formatted_value = f"{value:.1f}" if isinstance(value, (int, float)) and value != int(
                        value) else str(value)
                    html += f'<td style="border: 1px solid #ddd; padding: 8px; text-align: center; {style}">{formatted_value}</td>'
                else:
                    formatted_value = f"{value:.1f}" if isinstance(value, (int, float)) and value != int(
                        value) else str(value)
                    if row['PitchType'] == 'TOTAL':
                        html += f'<td style="border: 1px solid #ddd; padding: 8px; text-align: center; font-weight: bold; background-color: #f0f0f0;">{formatted_value}</td>'
                    else:
                        html += f'<td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{formatted_value}</td>'
            html += '</tr>'

        html += '</tbody></table>'
        html += SORTABLE_TABLE_JS
        html += f'<script>setTimeout(() => makeSortable("{table_id}"), 100);</script>'
        return ui.HTML(html)

    def _plotly_layout(title_text):
        """Shared dark Plotly layout for all plots."""
        return dict(
            plot_bgcolor="#1A1A1A",
            paper_bgcolor="#1A1A1A",
            font=dict(family="Barlow, sans-serif", color="#E8E8E8", size=11),
            title=dict(text=title_text, font=dict(color="#FDBB30", size=13,
                       family="Barlow Condensed, sans-serif"), x=0.5, xanchor="center"),
            legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#E8E8E8", size=10),
                        bordercolor="#3A3A3A", borderwidth=1),
            margin=dict(l=50, r=20, t=50, b=50),
            height=420,
        )

    def _axis_style(title="", zeroline=False, **kwargs):
        return dict(title=dict(text=title, font=dict(color="#999999", size=11)),
                    tickfont=dict(color="#999999", size=10),
                    gridcolor="#3A3A3A", gridwidth=0.5,
                    zerolinecolor="#555555", zerolinewidth=1,
                    zeroline=zeroline,
                    showline=False, **kwargs)

    def _plotly_html(fig):
        return ui.HTML(fig.to_html(full_html=False, include_plotlyjs=False,
                                   config={"displayModeBar": False}))

    def _ellipse_trace(x, y, color, n_std=1.0):
        """Return a Plotly scatter trace drawing a confidence ellipse."""
        valid = ~(np.isnan(x) | np.isnan(y))
        x, y = x[valid], y[valid]
        if len(x) < 3:
            return None
        try:
            cov = np.cov(x, y)
            if cov.ndim < 2:
                return None
            eigvals, eigvecs = np.linalg.eigh(cov)
            order = eigvals.argsort()[::-1]
            eigvals, eigvecs = eigvals[order], eigvecs[:, order]
            if np.any(eigvals <= 0):
                return None
            angle = np.arctan2(eigvecs[1, 0], eigvecs[0, 0])
            w, h = 2 * n_std * np.sqrt(eigvals)
            t = np.linspace(0, 2 * np.pi, 120)
            ell_x = w / 2 * np.cos(t)
            ell_y = h / 2 * np.sin(t)
            rot_x = np.cos(angle) * ell_x - np.sin(angle) * ell_y + np.mean(x)
            rot_y = np.sin(angle) * ell_x + np.cos(angle) * ell_y + np.mean(y)
            return go.Scatter(x=rot_x, y=rot_y, mode="lines",
                              line=dict(color=color, width=1.5, dash="dot"),
                              fill="toself", fillcolor=color,
                              opacity=0.15, showlegend=False, hoverinfo="skip")
        except Exception:
            return None

    def create_plot(plot_type, title="", pitch_call_filter=None):
        import plotly.graph_objects as go

        data = filtered_data()
        view_mode = input.view_mode()

        if view_mode:
            display_name = "KEN_OWL Team"
        else:
            pitcher = input.pitcher_id()
            if not pitcher:
                return ui.div()
            display_name = pitcher

        if data.empty:
            return ui.div()
        pitcher = display_name

        # ── Movement ─────────────────────────────────────────────────────────
        if plot_type == "movement":
            if not all(col in data.columns for col in ["HorzBreak", "InducedVertBreak", "PitchType"]):
                return ui.div("Required columns for movement plot not found")

            color_by = input.movement_color_by()
            traces = []

            if color_by == "arm_angle" and "arm_angle_type" in data.columns:
                groups = data["arm_angle_type"].dropna().unique()
                color_map = {g: arm_angle_colors.get(g, "#9C8975") for g in groups}
                legend_key = "Arm Angle Type"
                for g in groups:
                    sub = data[data["arm_angle_type"] == g]
                    c = color_map[g]
                    traces.append(go.Scatter(
                        x=sub["HorzBreak"], y=sub["InducedVertBreak"],
                        mode="markers", name=g,
                        marker=dict(color=c, size=5, opacity=0.6),
                        hovertemplate=f"<b>{g}</b><br>HB: %{{x:.1f}}<br>IVB: %{{y:.1f}}<extra></extra>"))
                    ell = _ellipse_trace(sub["HorzBreak"].values, sub["InducedVertBreak"].values, c)
                    if ell:
                        traces.append(ell)
            else:
                groups = data["PitchType"].unique()
                color_map = {p: pitch_colors_dict.get(p, "#9C8975") for p in groups}
                legend_key = "Pitch Type"
                for p in groups:
                    sub = data[data["PitchType"] == p]
                    c = color_map[p]
                    traces.append(go.Scatter(
                        x=sub["HorzBreak"], y=sub["InducedVertBreak"],
                        mode="markers", name=p,
                        marker=dict(color=c, size=5, opacity=0.6),
                        hovertemplate=f"<b>{p}</b><br>HB: %{{x:.1f}}<br>IVB: %{{y:.1f}}<extra></extra>"))
                    ell = _ellipse_trace(sub["HorzBreak"].values, sub["InducedVertBreak"].values, c)
                    if ell:
                        traces.append(ell)

            # Zero lines + optional arm angle ray
            shapes = [
                dict(type="line", x0=-25, x1=25, y0=0, y1=0,
                     line=dict(color="#555555", width=1)),
                dict(type="line", x0=0, x1=0, y0=-25, y1=25,
                     line=dict(color="#555555", width=1)),
            ]
            annotations = []
            if "arm_angle" in data.columns and not data["arm_angle"].isna().all():
                avg_arm_angle = data["arm_angle"].mean()
                corrected = 90 - avg_arm_angle
                angle_rad = np.radians(corrected)
                x_end = np.cos(angle_rad) * 25
                y_end = np.sin(angle_rad) * 25
                pitcher_hand = None
                for col in ["PitcherThrows", "pitcherHand"]:
                    if col in data.columns and not data[col].isna().all():
                        pitcher_hand = data[col].iloc[0]
                        break
                if pitcher_hand and str(pitcher_hand).upper().startswith("L"):
                    x_end *= -1
                shapes.append(dict(type="line", x0=0, x1=x_end, y0=0, y1=y_end,
                                   line=dict(color="#FDBB30", width=1.5, dash="dash")))
                annotations.append(dict(x=25, y=-23, text=f"{corrected:.1f}°",
                                        showarrow=False, font=dict(color="#FDBB30", size=10),
                                        xanchor="right"))

            title_suffix = "by Arm Angle" if color_by == "arm_angle" else "by Pitch Type"
            fig = go.Figure(traces)
            fig.update_layout(**_plotly_layout(f"{pitcher}: Pitch Movement ({title_suffix})"),
                              shapes=shapes, annotations=annotations)
            fig.update_xaxes(**_axis_style("Horz Break (in)"), range=[-25, 25])
            fig.update_yaxes(**_axis_style("Vert Break (in)"), range=[-25, 25])
            return _plotly_html(fig)

        # ── Release point ─────────────────────────────────────────────────────
        elif plot_type == "release":
            if not all(col in data.columns for col in ["RelSide", "RelHeight", "PitchType"]):
                return ui.div()
            traces = []
            for p in data["PitchType"].unique():
                sub = data[data["PitchType"] == p]
                c = pitch_colors_dict.get(p, "#9C8975")
                traces.append(go.Scatter(
                    x=sub["RelSide"], y=sub["RelHeight"],
                    mode="markers", name=p,
                    marker=dict(color=c, size=5, opacity=0.6),
                    hovertemplate=f"<b>{p}</b><br>Side: %{{x:.2f}}<br>Ht: %{{y:.2f}}<extra></extra>"))
            fig = go.Figure(traces)
            fig.update_layout(**_plotly_layout(f"{display_name}: Release Metrics"))
            fig.update_xaxes(**_axis_style("Rel Side (ft)"), range=[-4, 4])
            fig.update_yaxes(**_axis_style("Rel Height (ft)"), range=[0, 8])
            return _plotly_html(fig)

        # ── Velocity distribution (KDE) ───────────────────────────────────────
        elif plot_type == "velocity":
            if "RelSpeed" not in data.columns:
                return ui.div()
            traces = []
            all_velocities = data["RelSpeed"].dropna()
            if len(all_velocities) > 0:
                vel_min = all_velocities.min() - 2
                vel_max = all_velocities.max() + 2
                vel_range = np.linspace(vel_min, vel_max, 200)
                for p in data["PitchType"].unique():
                    sub = pd.to_numeric(data[data["PitchType"] == p]["RelSpeed"], errors="coerce").dropna()
                    if len(sub) > 1:
                        density = simple_kde(sub.values, vel_range)
                        c = pitch_colors_dict.get(p, "#9C8975")
                        # Convert any color to rgba with 0.25 alpha
                        if c.startswith("#") and len(c) == 7:
                            r = int(c[1:3], 16)
                            g_val = int(c[3:5], 16)
                            b_val = int(c[5:7], 16)
                            fill_c = f"rgba({r},{g_val},{b_val},0.25)"
                        elif c.startswith("rgb("):
                            fill_c = c.replace("rgb(", "rgba(").replace(")", ",0.25)")
                        else:
                            fill_c = "rgba(150,150,150,0.25)"
                        traces.append(go.Scatter(
                            x=vel_range, y=density, mode="lines", name=p,
                            line=dict(color=c, width=2),
                            fill="tozeroy", fillcolor=fill_c,
                            hovertemplate=f"<b>{p}</b><br>%{{x:.1f}} mph<extra></extra>"))
            fig = go.Figure(traces)
            fig.update_layout(**_plotly_layout(f"{display_name}: Velocity Distribution"))
            fig.update_xaxes(**_axis_style("Rel Speed (mph)"))
            fig.update_yaxes(**_axis_style("Density"))
            return _plotly_html(fig)

        # ── Arm angle release ─────────────────────────────────────────────────
        elif plot_type == "arm_angle":
            if not all(col in data.columns for col in ["RelSide", "RelHeight"]):
                return ui.div("Release point data not available")
            traces = []
            shapes = []
            if "arm_angle_type" in data.columns:
                for g in data["arm_angle_type"].dropna().unique():
                    sub = data[data["arm_angle_type"] == g]
                    avg_angle = sub["arm_angle"].mean() if "arm_angle" in sub.columns else 0
                    c = arm_angle_colors.get(g, "#9C8975")
                    traces.append(go.Scatter(
                        x=sub["RelSide"], y=sub["RelHeight"],
                        mode="markers", name=f"{g} ({avg_angle:.1f}°)",
                        marker=dict(color=c, size=6, opacity=0.7),
                        hovertemplate=f"<b>{g}</b><br>Side: %{{x:.2f}}<br>Ht: %{{y:.2f}}<extra></extra>"))
            else:
                for p in data["PitchType"].unique():
                    sub = data[data["PitchType"] == p]
                    c = pitch_colors_dict.get(p, "#9C8975")
                    traces.append(go.Scatter(
                        x=sub["RelSide"], y=sub["RelHeight"],
                        mode="markers", name=p,
                        marker=dict(color=c, size=6, opacity=0.7),
                        hovertemplate=f"<b>{p}</b><br>Side: %{{x:.2f}}<br>Ht: %{{y:.2f}}<extra></extra>"))
            if "shoulder_pos" in data.columns and not data["shoulder_pos"].isna().all():
                sh = data["shoulder_pos"].iloc[0] / 12
                shapes.append(dict(type="line", x0=-4, x1=4, y0=sh, y1=sh,
                                   line=dict(color="#FF6B6B", width=1.5, dash="dash")))
                traces.append(go.Scatter(x=[None], y=[None], mode="lines", name="Shoulder Ht",
                                         line=dict(color="#FF6B6B", dash="dash")))
            legend_title = "Arm Angle Type" if "arm_angle_type" in data.columns else "Pitch Type"
            fig = go.Figure(traces)
            fig.update_layout(**_plotly_layout(f"{pitcher}: Release Point by Arm Angle"),
                              shapes=shapes)
            fig.update_xaxes(**_axis_style("Rel Side (ft)"), range=[-4, 4])
            fig.update_yaxes(**_axis_style("Rel Height (ft)"), range=[0, 8])
            return _plotly_html(fig)

        # ── Location plots ────────────────────────────────────────────────────
        elif plot_type in ["location", "strike_swinging", "called_strike", "called_ball", "chase"]:
            if plot_type == "chase" and "Chase" in data.columns:
                plot_data = data[data["Chase"] == 1]
            elif pitch_call_filter:
                if "PitchCall" not in data.columns:
                    return ui.div()
                plot_data = (data[data["PitchCall"].isin(pitch_call_filter)]
                             if isinstance(pitch_call_filter, list)
                             else data[data["PitchCall"] == pitch_call_filter])
            else:
                plot_data = data

            if plot_data.empty:
                return ui.div(f"No data available for {title}")
            if not all(col in plot_data.columns for col in ["PlateLocSide", "PlateLocHeight", "PitchType"]):
                return ui.div()

            traces = []
            for p in plot_data["PitchType"].unique():
                sub = plot_data[plot_data["PitchType"] == p]
                c = pitch_colors_dict.get(p, "#9C8975")
                traces.append(go.Scatter(
                    x=sub["PlateLocSide"], y=sub["PlateLocHeight"],
                    mode="markers", name=p,
                    marker=dict(color=c, size=5, opacity=0.6),
                    hovertemplate=f"<b>{p}</b><br>Side: %{{x:.2f}}<br>Ht: %{{y:.2f}}<extra></extra>"))

            # Strike zone rectangle
            sz_shapes = [
                dict(type="rect", x0=-0.85, x1=0.85, y0=1.6, y1=3.4,
                     line=dict(color="#4A90D9", width=2), fillcolor="rgba(0,0,0,0)"),
                # Home plate
                dict(type="path",
                     path="M -0.625 0.5 L 0.625 0.5 L 0.608 0.625 L 0 0.708 L -0.608 0.625 Z",
                     line=dict(color="#4A90D9", width=1.5), fillcolor="rgba(0,0,0,0)"),
            ]

            fig = go.Figure(traces)
            fig.update_layout(**_plotly_layout(f"{pitcher}: {title}"), shapes=sz_shapes)
            fig.update_xaxes(**_axis_style("Hor Loc"), range=[-3.5, 3.5])
            fig.update_yaxes(**_axis_style("Vert Loc"), range=[0, 5.5])
            return _plotly_html(fig)

        return ui.div(f"Unknown plot type: {plot_type}")

    def create_tunneling_plot(plot_type):
        import plotly.graph_objects as go

        data = filtered_data()
        view_mode = input.view_mode()

        if view_mode:
            display_name = "KEN_OWL Team"
        else:
            pitcher = input.pitcher_id()
            if not pitcher:
                return ui.div("No data available")
            display_name = pitcher

        if data.empty:
            return ui.div("No data available")

        if plot_type != "release_angles":
            return ui.div("Plot type not available")

        required_cols = ["VertRelAngle", "HorzRelAngle", "PitchType"]
        alt_cols_map = {"VertRelAngle": ["VerticalRelAngle", "VRA"],
                        "HorzRelAngle": ["HorizontalRelAngle", "HRA"]}
        missing_cols = []

        for col in required_cols:
            if col not in data.columns:
                found = False
                for alt in alt_cols_map.get(col, []):
                    if alt in data.columns:
                        data = data.rename(columns={alt: col})
                        found = True
                        break
                if not found:
                    missing_cols.append(col)

        if missing_cols:
            return ui.div(f"Missing required columns: {', '.join(missing_cols)}")

        for col in ["VertRelAngle", "HorzRelAngle"]:
            data[col] = pd.to_numeric(data[col], errors="coerce")

        data_clean = data.dropna(subset=["HorzRelAngle", "VertRelAngle", "PitchType"])
        if data_clean.empty:
            return ui.div("No valid data for release angles plot")

        traces = []
        for p in data_clean["PitchType"].unique():
            sub = data_clean[data_clean["PitchType"] == p]
            if len(sub) < 2:
                continue
            c = pitch_colors_dict.get(p, "#9C8975")
            x = sub["HorzRelAngle"].values
            y = sub["VertRelAngle"].values

            traces.append(go.Scatter(
                x=x, y=y, mode="markers", name=p,
                marker=dict(color=c, size=5, opacity=0.35),
                hovertemplate=f"<b>{p}</b><br>HorzAngle: %{{x:.2f}}<br>VertAngle: %{{y:.2f}}<extra></extra>"))

            ell = _ellipse_trace(x, y, c)
            if ell:
                traces.append(ell)

            # Mean marker
            traces.append(go.Scatter(
                x=[x.mean()], y=[y.mean()], mode="markers", name=f"{p} mean",
                marker=dict(symbol="x", color=c, size=10, line=dict(width=2, color="#E8E8E8")),
                showlegend=False,
                hovertemplate=f"<b>{p} mean</b><br>HorzAngle: {x.mean():.2f}<br>VertAngle: {y.mean():.2f}<extra></extra>"))

        shapes = [
            dict(type="line", x0=data_clean["HorzRelAngle"].min() - 1,
                 x1=data_clean["HorzRelAngle"].max() + 1, y0=0, y1=0,
                 line=dict(color="#555555", width=1)),
            dict(type="line", x0=0, x1=0,
                 y0=data_clean["VertRelAngle"].min() - 1, y1=data_clean["VertRelAngle"].max() + 1,
                 line=dict(color="#555555", width=1)),
        ]

        fig = go.Figure(traces)
        fig.update_layout(**_plotly_layout(f"{display_name}: Release Angles (Tunneling)"),
                          shapes=shapes)
        fig.update_xaxes(**_axis_style("Horizontal Release Angle"))
        fig.update_yaxes(**_axis_style("Vertical Release Angle"))
        return _plotly_html(fig)

    def create_tunneling_metrics_table():
        data = filtered_data()
        view_mode = input.view_mode()

        if view_mode:
            display_name = "KEN_OWL Team"
        else:
            pitcher = input.pitcher_id()
            if not pitcher:
                return ui.div("No data available")
            display_name = pitcher

        if data.empty:
            return ui.div("No data available")

        pitcher = display_name

        # Check for required columns
        required_cols = ["PitchType"]
        if not all(col in data.columns for col in required_cols):
            return ui.div("Required columns missing for tunneling metrics")

        # Calculate tunneling metrics by pitch type
        pitch_types = data["PitchType"].unique()
        metrics_list = []

        for pitch_type in pitch_types:
            subset = data[data["PitchType"] == pitch_type]
            if len(subset) < 2:
                continue

            metric_row = {'PitchType': pitch_type, 'Count': len(subset)}

            # Release point consistency (standard deviation)
            if all(col in subset.columns for col in ["RelSide", "RelHeight"]):
                metric_row["Rel Side σ"] = subset["RelSide"].std().round(3) if len(subset) > 1 else 0.0
                metric_row["Rel Height σ"] = subset["RelHeight"].std().round(3) if len(subset) > 1 else 0.0

            # Release angle consistency
            if all(col in subset.columns for col in ["HorzRelAngle", "VertRelAngle"]):
                metric_row["Horz Angle σ"] = subset["HorzRelAngle"].std().round(3) if len(subset) > 1 else 0.0
                metric_row["Vert Angle σ"] = subset["VertRelAngle"].std().round(3) if len(subset) > 1 else 0.0

            # Plate location separation (standard deviation - higher is better for deception)
            if all(col in subset.columns for col in ["PlateLocSide", "PlateLocHeight"]):
                metric_row["Plate Side σ"] = subset["PlateLocSide"].std().round(3) if len(subset) > 1 else 0.0
                metric_row["Plate Height σ"] = subset["PlateLocHeight"].std().round(3) if len(subset) > 1 else 0.0

            metrics_list.append(metric_row)

        if not metrics_list:
            return ui.div("Insufficient data for tunneling metrics")

        metrics_df = pd.DataFrame(metrics_list)

        def get_consistency_color(value, col_name, is_plate_metric=False):
            if pd.isna(value) or value == 0:
                return "background-color: #f8f9fa; color: #333;"

            # For plate location metrics, HIGHER is better (more deception)
            if is_plate_metric:
                # Typical ranges: 0.3-1.2 for plate side, 0.3-0.8 for plate height
                if "Side" in col_name:
                    min_val, max_val = 0.3, 1.2
                else:  # Height
                    min_val, max_val = 0.3, 0.8

                # Normalize (higher is better for plate metrics)
                normalized = (value - min_val) / (max_val - min_val) if max_val > min_val else 0.5
            else:
                # For release metrics, LOWER is better (more consistency)
                # Typical ranges: 0.05-0.3 for release side/height, 0.5-3.0 for angles
                if "Angle" in col_name:
                    min_val, max_val = 0.5, 3.0
                else:  # Release side/height
                    min_val, max_val = 0.05, 0.3

                # Normalize (lower is better for release metrics - invert)
                normalized = 1 - ((value - min_val) / (max_val - min_val)) if max_val > min_val else 0.5

            normalized = max(0, min(1, normalized))

            # Create gradient color (RED = good, white = neutral, BLUE = bad) - INVERTED
            if normalized < 0.5:
                # Blue to white gradient (bad to neutral)
                factor = normalized * 2
                r = int(0 + (248 - 0) * factor)
                g = int(123 + (249 - 123) * factor)
                b = int(255 + (250 - 255) * factor)
                text_color = "white" if normalized < 0.2 else "#333"
                font_weight = "bold" if normalized < 0.3 else "normal"
            else:
                # White to red gradient (neutral to good)
                factor = (normalized - 0.5) * 2
                r = int(248 + (220 - 248) * factor)
                g = int(249 + (53 - 249) * factor)
                b = int(250 + (69 - 250) * factor)
                text_color = "#333" if normalized < 0.7 else "white"
                font_weight = "normal" if normalized < 0.7 else "bold"

            return f"background-color: rgb({r}, {g}, {b}); color: {text_color}; font-weight: {font_weight};"

        # Create HTML table
        table_id = "tunneling_metrics_table_" + str(hash(display_name) % 10000)
        html = f'<table id="{table_id}" style="border-collapse: collapse; width: 100%; font-size: 14px;">'
        html += '<thead><tr>'
        for col in metrics_df.columns:
            html += f'<th style="border: 1px solid #ddd; padding: 8px; background-color: #f8f9fa;">{col}</th>'
        html += '</tr></thead><tbody>'

        for _, row in metrics_df.iterrows():
            html += '<tr>'
            for col, value in row.items():
                if col == 'PitchType':
                    color = pitch_colors_dict.get(value, "#9C8975")
                    html += f'<td style="border: 1px solid #ddd; padding: 6px; background-color: {color}; color: white; font-weight: bold; text-align: center; border-radius: 4px;">{value}</td>'
                elif col == 'Count':
                    html += f'<td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{value}</td>'
                else:
                    # Apply color gradient based on metric type
                    is_plate = "Plate" in col
                    style = get_consistency_color(value, col, is_plate)
                    formatted_value = f"{value:.3f}" if isinstance(value, float) else str(value)
                    html += f'<td style="border: 1px solid #ddd; padding: 8px; text-align: center; {style}">{formatted_value}</td>'
            html += '</tr>'

        html += '</tbody></table>'
        html += '<p style="font-size: 11px; color: #666; margin-top: 10px; font-style: italic;">σ = standard deviation. <strong>Release metrics:</strong> Lower = more consistent (red is good). <strong>Plate location metrics:</strong> Higher = better separation/deception (red is good).</p>'
        html += SORTABLE_TABLE_JS
        html += f'<script>setTimeout(() => makeSortable("{table_id}"), 100);</script>'

        return ui.HTML(html)

    def create_leaderboard_metrics_table():
        """Create leaderboard showing pitch metrics for all KEN_OWL pitchers"""
        data = leaderboard_data()
        pitch_type_filter = input.leaderboard_pitch_type()
        pitch_types_multi = input.leaderboard_pitch_types_multi()
        min_pitches = input.min_pitches() or 50

        if data.empty:
            return ui.div("No data available")

        required_cols = ["PitchType", "Pitcher", "RelSpeed"]
        missing_cols = [col for col in required_cols if col not in data.columns]
        if missing_cols:
            return ui.div(f"Required columns missing: {missing_cols}")

        # Filter by pitch type
        if pitch_type_filter == "TOTAL":
            # When TOTAL is selected, filter by the multi-select pitch types
            if pitch_types_multi:
                data = data[data["PitchType"].isin(pitch_types_multi)]
            grouped = data.groupby("Pitcher")
            pitch_type_display = f"TOTAL ({', '.join(pitch_types_multi) if pitch_types_multi else 'All'})"
        else:
            data = data[data["PitchType"] == pitch_type_filter]
            if data.empty:
                return ui.div(f"No data available for {pitch_type_filter}")
            grouped = data.groupby("Pitcher")
            pitch_type_display = pitch_type_filter

        # Convert numeric columns
        numeric_cols = ["RelSpeed", "InducedVertBreak", "HorzBreak", "SpinRate", "RelHeight", "RelSide", "Extension",
                        "VertApprAngle", "HorzApprAngle"]
        if "Tilt" in data.columns:
            numeric_cols.append("Tilt")
        if "arm_angle" in data.columns:
            numeric_cols.append("arm_angle")

        for col in numeric_cols:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors="coerce")

        # Calculate metrics for each pitcher
        pitcher_metrics = []

        for pitcher_name, pitcher_data in grouped:
            if len(pitcher_data) < min_pitches:
                continue

            metrics = {'Pitcher': pitcher_name, 'Count': len(pitcher_data)}

            # Build aggregation dictionary
            agg_dict = {
                "AvgVelo": ("RelSpeed", "mean"),
                "InducedVertBreak": ("InducedVertBreak", "mean"),
                "HorzBreak": ("HorzBreak", "mean"),
                "SpinRate": ("SpinRate", "mean"),
                "RelHeight": ("RelHeight", "mean"),
                "RelSide": ("RelSide", "mean"),
                "Extension": ("Extension", "mean"),
                "VertApprAngle": ("VertApprAngle", "mean"),
                "HorzApprAngle": ("HorzApprAngle", "mean")
            }

            # Calculate aggregates
            for key, (col, func) in agg_dict.items():
                if col in pitcher_data.columns:
                    val = pitcher_data[col].agg(func)
                    metrics[key] = float(val) if not pd.isna(val) else 0.0
                else:
                    metrics[key] = 0.0

            # Add Tilt if available
            if "Tilt" in pitcher_data.columns and pitcher_data["Tilt"].notna().sum() > 0:
                metrics["Tilt"] = float(pitcher_data["Tilt"].mean())

            # Add ArmAngle if available
            if "arm_angle" in pitcher_data.columns:
                metrics["ArmAngle"] = float(90 - pitcher_data["arm_angle"].mean())

            # Max velocity
            metrics["MaxVelo"] = float(pitcher_data["RelSpeed"].max())

            # Usage percentage (only relevant if filtering by pitch type)
            if pitch_type_filter != "TOTAL":
                total_pitches = len(data[data["Pitcher"] == pitcher_name])
                metrics["Usage%"] = (len(pitcher_data) / total_pitches * 100) if total_pitches > 0 else 0.0

            pitcher_metrics.append(metrics)

        if not pitcher_metrics:
            return ui.div(f"No pitchers with at least {min_pitches} pitches of {pitch_type_display}")

        # Convert to DataFrame and round
        pitcher_metrics_df = pd.DataFrame(pitcher_metrics)

        # Rename columns
        pitcher_metrics_df = pitcher_metrics_df.rename(columns={
            "InducedVertBreak": "IVB", "HorzBreak": "HB", "VertApprAngle": "VAA",
            "HorzApprAngle": "HAA", "AvgVelo": "Vel"
        })

        # Build column order
        column_order = ["Pitcher", "Count"]
        if "Usage%" in pitcher_metrics_df.columns:
            column_order.append("Usage%")

        column_order.extend(["Vel", "MaxVelo", "IVB", "HB", "SpinRate"])

        if "Tilt" in pitcher_metrics_df.columns:
            column_order.append("Tilt")

        column_order.extend(["RelHeight", "RelSide", "VAA", "HAA", "Extension"])

        if "ArmAngle" in pitcher_metrics_df.columns:
            column_order.insert(-3, "ArmAngle")

        # Select and order columns
        available_cols = [col for col in column_order if col in pitcher_metrics_df.columns]
        pitcher_metrics_df = pitcher_metrics_df[available_cols]

        # Round numeric columns
        numeric_cols_to_round = ["Vel", "MaxVelo", "IVB", "HB", "SpinRate", "RelHeight", "RelSide",
                                 "VAA", "HAA", "Extension", "Usage%"]
        if "Tilt" in pitcher_metrics_df.columns:
            numeric_cols_to_round.append("Tilt")
        if "ArmAngle" in pitcher_metrics_df.columns:
            numeric_cols_to_round.append("ArmAngle")

        for col in numeric_cols_to_round:
            if col in pitcher_metrics_df.columns:
                pitcher_metrics_df[col] = pitcher_metrics_df[col].round(1)

        # Sort by Vel (descending)
        pitcher_metrics_df = pitcher_metrics_df.sort_values("Vel", ascending=False)

        # Create HTML table
        table_id = "leaderboard_metrics_table_" + str(hash(pitch_type_filter) % 10000)
        html = f'<table id="{table_id}" style="border-collapse: collapse; width: 100%; font-size: 14px;">'
        html += '<thead><tr>'
        for col in pitcher_metrics_df.columns:
            html += f'<th style="border: 1px solid #ddd; padding: 8px; background-color: #f8f9fa;">{col}</th>'
        html += '</tr></thead><tbody>'

        for _, row in pitcher_metrics_df.iterrows():
            html += '<tr>'
            for col, value in row.items():
                if col == 'Pitcher':
                    html += f'<td style="border: 1px solid #ddd; padding: 8px; text-align: left; font-weight: bold;">{value}</td>'
                elif col in ['Vel', 'Extension'] and value != 0:
                    style = get_performance_color(value, pitch_type_display, col)
                    formatted_value = f"{value:.1f}" if isinstance(value, (int, float)) and value != int(
                        value) else str(value)
                    html += f'<td style="border: 1px solid #ddd; padding: 8px; text-align: center; {style}">{formatted_value}</td>'
                else:
                    formatted_value = f"{value:.1f}" if isinstance(value, (int, float)) and value != int(
                        value) else str(value)
                    html += f'<td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{formatted_value}</td>'
            html += '</tr>'

        html += '</tbody></table>'
        html += SORTABLE_TABLE_JS
        html += f'<script>setTimeout(() => makeSortable("{table_id}"), 100);</script>'
        html += f'<p style="font-size: 12px; color: #666; margin-top: 10px;"><strong>Showing:</strong> {pitch_type_display} | <strong>Min Pitches:</strong> {min_pitches} | <strong>Pitchers:</strong> {len(pitcher_metrics_df)}</p>'

        return ui.HTML(html)

    def create_leaderboard_stats_table():
        data = leaderboard_data()
        pitch_type_filter = input.leaderboard_pitch_type()
        pitch_types_multi = input.leaderboard_pitch_types_multi()
        min_pitches = input.min_pitches() or 50

        if data.empty:
            return ui.div("No data available")

        required_cols = ["PitchType", "Pitcher", "PitchCall"]
        missing_cols = [col for col in required_cols if col not in data.columns]
        if missing_cols:
            return ui.div(f"Required columns missing: {missing_cols}")

        # Filter by pitch type
        if pitch_type_filter == "TOTAL":
            # When TOTAL is selected, filter by the multi-select pitch types
            if pitch_types_multi:
                data = data[data["PitchType"].isin(pitch_types_multi)]
            grouped = data.groupby("Pitcher")
            pitch_type_display = f"TOTAL ({', '.join(pitch_types_multi) if pitch_types_multi else 'All'})"
        else:
            data = data[data["PitchType"] == pitch_type_filter]
            if data.empty:
                return ui.div(f"No data available for {pitch_type_filter}")
            grouped = data.groupby("Pitcher")
            pitch_type_display = pitch_type_filter

        # Calculate stats for each pitcher with corrected logic
        pitcher_stats = []

        for pitcher_name, pitcher_data in grouped:
            if len(pitcher_data) < min_pitches:
                continue

            stats = {'Pitcher': pitcher_name, 'Count': len(pitcher_data)}

            # Exit velocity and launch angle - only from balls in play
            in_play_pitcher = pitcher_data[pitcher_data["PitchCall"] == "InPlay"]
            if "ExitSpeed" in pitcher_data.columns and not in_play_pitcher.empty:
                exit_speeds = in_play_pitcher["ExitSpeed"].dropna()
                stats["ExitVel"] = float(exit_speeds.mean()) if len(exit_speeds) > 0 else 0.0
            else:
                stats["ExitVel"] = 0.0

            if "Angle" in pitcher_data.columns and not in_play_pitcher.empty:
                angles = in_play_pitcher["Angle"].dropna()
                stats["LaunchAng"] = float(angles.mean()) if len(angles) > 0 else 0.0
            else:
                stats["LaunchAng"] = 0.0

            # Calculate batted ball percentages
            if "Angle" in pitcher_data.columns:
                in_play_data = pitcher_data[pitcher_data["PitchCall"] == "InPlay"].copy()
                if not in_play_data.empty:
                    # Ground balls: < 10 degrees
                    gb_count = len(in_play_data[in_play_data["Angle"] < 10])

                    # Line drives: 10-25 degrees
                    ld_count = len(in_play_data[(in_play_data["Angle"] >= 10) & (in_play_data["Angle"] <= 25)])

                    # Fly balls: > 25 degrees
                    fb_data = in_play_data[in_play_data["Angle"] > 25]
                    fb_count = len(fb_data)

                    # Home runs - use PlayResult column if available
                    if "PlayResult" in data.columns:
                        hr_data = in_play_data[in_play_data["PlayResult"] == "HomeRun"]
                    else:
                        # Fallback methods if PlayResult not available
                        if "ExitSpeed" in data.columns:
                            hr_data = fb_data[(fb_data["ExitSpeed"] > 95)]
                        else:
                            hr_data = fb_data[fb_data["Angle"] > 35]  # Very high angle as proxy

                    hr_count = len(hr_data)

                    total_bip = len(in_play_data)

                    # Calculate percentages
                    stats["GB%"] = (gb_count / total_bip * 100) if total_bip > 0 else 0.0
                    stats["LD%"] = (ld_count / total_bip * 100) if total_bip > 0 else 0.0
                    stats["FB%"] = (fb_count / total_bip * 100) if total_bip > 0 else 0.0

                    # HR/FB% - home runs as percentage of fly balls
                    stats["HR/FB%"] = (hr_count / fb_count * 100) if fb_count > 0 else 0.0
                else:
                    stats["GB%"] = 0.0
                    stats["LD%"] = 0.0
                    stats["FB%"] = 0.0
                    stats["HR/FB%"] = 0.0
            else:
                stats["GB%"] = 0.0
                stats["LD%"] = 0.0
                stats["FB%"] = 0.0
                stats["HR/FB%"] = 0.0

            # First pitch strike percentage
            if "PitchofPA" in pitcher_data.columns:
                first_pitches = pitcher_data[pitcher_data["PitchofPA"] == 1]
                if len(first_pitches) > 0:
                    first_strikes = first_pitches[first_pitches["PitchCall"].isin([
                        "StrikeCalled", "StrikeSwinging", "FoulBall", "FoulBallNotFieldable", "InPlay"
                    ])]
                    stats["1PK%"] = (len(first_strikes) / len(first_pitches) * 100)
                else:
                    stats["1PK%"] = 0.0

                # 2of3% calculation - Modified logic
                if "CustomGameID" in pitcher_data.columns or "Inning" in pitcher_data.columns:
                    groupby_cols = []
                    if "CustomGameID" in pitcher_data.columns:
                        groupby_cols.append("CustomGameID")
                    if "Inning" in pitcher_data.columns:
                        groupby_cols.append("Inning")
                    if "PAofInning" in pitcher_data.columns:
                        groupby_cols.append("PAofInning")
                    elif "Batter" in pitcher_data.columns:
                        groupby_cols.append("Batter")

                    if groupby_cols:
                        ab_groups = pitcher_data.groupby(groupby_cols)

                        two_of_three_count = 0
                        total_ab_count = 0

                        for ab_id, ab_data in ab_groups:
                            if len(ab_data) >= 2:
                                # Get first three pitches
                                first_three = ab_data[ab_data["PitchofPA"].isin([1, 2, 3])].sort_values("PitchofPA")

                                if len(first_three) >= 2:
                                    counts_success = True

                                    # Check each pitch for disqualifying conditions
                                    for idx, pitch in first_three.iterrows():
                                        pitch_num = pitch["PitchofPA"]
                                        pitch_call = pitch["PitchCall"]

                                        # Count balls and strikes up to this point
                                        pitches_so_far = first_three[first_three["PitchofPA"] <= pitch_num]
                                        balls = len(pitches_so_far[pitches_so_far["PitchCall"].isin(["BallCalled"])])
                                        strikes = len(pitches_so_far[pitches_so_far["PitchCall"].isin([
                                            "StrikeCalled", "StrikeSwinging", "FoulBall", "FoulBallNotFieldable"
                                        ])])

                                        # HBP never counts
                                        if pitch_call == "HitByPitch":
                                            counts_success = False
                                            break

                                        # 2-0 count never counts
                                        if balls == 2 and strikes == 0:
                                            counts_success = False
                                            break

                                        # 1-0 base hit never counts
                                        if balls == 1 and strikes == 0 and pitch_call == "InPlay":
                                            if "PlayResult" in ab_data.columns:
                                                play_result = pitch.get("PlayResult", "")
                                                if play_result and "Out" not in str(play_result):
                                                    counts_success = False
                                                    break
                                            else:
                                                # Without PlayResult, assume InPlay at 1-0 is a hit
                                                counts_success = False
                                                break

                                    # Check if achieved 2 strikes in first 3 pitches
                                    first_three_strikes = first_three["PitchCall"].isin([
                                        "StrikeCalled", "StrikeSwinging", "FoulBall", "FoulBallNotFieldable", "InPlay"
                                    ])

                                    total_ab_count += 1

                                    if first_three_strikes.sum() >= 2 and counts_success:
                                        two_of_three_count += 1

                        stats["2of3%"] = (two_of_three_count / total_ab_count * 100) if total_ab_count > 0 else 0.0
                    else:
                        stats["2of3%"] = 0.0
                else:
                    stats["2of3%"] = 0.0
            else:
                stats["1PK%"] = 0.0
                stats["2of3%"] = 0.0

            # Strike percentage
            all_strikes = pitcher_data[pitcher_data["PitchCall"].isin([
                "StrikeCalled", "StrikeSwinging", "FoulBall", "FoulBallNotFieldable", "InPlay"
            ])]
            stats["Strike%"] = (len(all_strikes) / len(pitcher_data) * 100)

            # Zone percentage
            if "inZone" in pitcher_data.columns:
                zone_pitches = pitcher_data[pitcher_data["inZone"] == 1]
                stats["Zone%"] = (len(zone_pitches) / len(pitcher_data) * 100)
            else:
                stats["Zone%"] = 0.0

            # Swinging strike percentage
            sw_strikes = pitcher_data[pitcher_data["PitchCall"] == "StrikeSwinging"]
            stats["SwStr%"] = (len(sw_strikes) / len(pitcher_data) * 100)

            # Whiff percentage (miss rate)
            swings = pitcher_data[pitcher_data["PitchCall"].isin([
                "StrikeSwinging", "FoulBall", "FoulBallNotFieldable", "InPlay"
            ])]
            whiffs = pitcher_data[pitcher_data["PitchCall"] == "StrikeSwinging"]
            stats["Miss%"] = (len(whiffs) / len(swings) * 100) if len(swings) > 0 else 0.0

            # In-zone whiff percentage
            inzone_swings = pitcher_data[(pitcher_data["inZone"] == 1) & (pitcher_data["PitchCall"].isin([
                "StrikeSwinging", "FoulBall", "FoulBallNotFieldable", "InPlay"
            ]))]
            inzone_whiffs = pitcher_data[
                (pitcher_data["inZone"] == 1) & (pitcher_data["PitchCall"] == "StrikeSwinging")]
            stats["IZWhiff%"] = (len(inzone_whiffs) / len(inzone_swings) * 100) if len(inzone_swings) > 0 else 0.0

            pitcher_stats.append(stats)

        if not pitcher_stats:
            return ui.div(f"No pitchers with at least {min_pitches} pitches of {pitch_type_display}")

        # Convert to DataFrame and round
        pitcher_stats_df = pd.DataFrame(pitcher_stats)
        numeric_cols = ["ExitVel", "LaunchAng", "1PK%", "2of3%", "Zone%", "Strike%", "SwStr%", "Miss%", "IZWhiff%",
                        "GB%", "LD%", "FB%"]
        for col in numeric_cols:
            if col in pitcher_stats_df.columns:
                pitcher_stats_df[col] = pd.to_numeric(pitcher_stats_df[col], errors='coerce').fillna(0.0).round(1)

        # Sort by Strike% (descending)
        pitcher_stats_df = pitcher_stats_df.sort_values("Strike%", ascending=False)

        # Create HTML table
        table_id = "leaderboard_stats_table_" + str(hash(pitch_type_filter) % 10000)
        html = f'<table id="{table_id}" style="border-collapse: collapse; width: 100%; font-size: 14px;">'
        html += '<thead><tr>'
        for col in pitcher_stats_df.columns:
            html += f'<th style="border: 1px solid #ddd; padding: 8px; background-color: #f8f9fa;">{col}</th>'
        html += '</tr></thead><tbody>'

        for _, row in pitcher_stats_df.iterrows():
            html += '<tr>'
            for col, value in row.items():
                if col == 'Pitcher':
                    html += f'<td style="border: 1px solid #ddd; padding: 8px; text-align: left; font-weight: bold;">{value}</td>'
                elif col in ['Miss%', '1PK%', '2of3%','Zone%', 'Strike%', 'SwStr%', 'IZWhiff%', 'ExitVel', 'LaunchAng', 'GB%',
                             'LD%', 'FB%'] and value != 0:
                    style = get_performance_color(value, pitch_type_display, col)
                    formatted_value = f"{value:.1f}" if isinstance(value, (int, float)) and value != int(
                        value) else str(value)
                    html += f'<td style="border: 1px solid #ddd; padding: 8px; text-align: center; {style}">{formatted_value}</td>'
                else:
                    formatted_value = f"{value:.1f}" if isinstance(value, (int, float)) and value != int(
                        value) else str(value)
                    html += f'<td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{formatted_value}</td>'
            html += '</tr>'

        html += '</tbody></table>'
        html += SORTABLE_TABLE_JS
        html += f'<script>setTimeout(() => makeSortable("{table_id}"), 100);</script>'
        html += f'<p style="font-size: 12px; color: #666; margin-top: 10px;"><strong>Showing:</strong> {pitch_type_display} | <strong>Min Pitches:</strong> {min_pitches} | <strong>Pitchers:</strong> {len(pitcher_stats_df)}</p>'
        return ui.HTML(html)

    def create_usage_by_hand_plot():
        """Butterfly / tornado chart — Plotly: pitch usage % vs LHH (left) and RHH (right)."""
        import plotly.graph_objects as go

        data = filtered_data()
        view_mode = input.view_mode()

        if view_mode:
            display_name = "KEN_OWL Team"
        else:
            pitcher = input.pitcher_id()
            if not pitcher:
                return ui.div()
            display_name = pitcher

        if data.empty:
            return ui.div()

        if "BatterSide" not in data.columns or "PitchType" not in data.columns:
            return ui.div("BatterSide or PitchType column not found")

        lhh = data[data["BatterSide"] == "Left"]
        rhh = data[data["BatterSide"] == "Right"]
        n_lhh = len(lhh)
        n_rhh = len(rhh)

        if n_lhh == 0 and n_rhh == 0:
            return ui.div("No batter-hand data available")

        all_types = sorted(data["PitchType"].unique())
        lhh_pct = (lhh["PitchType"].value_counts(normalize=True) * 100).reindex(all_types, fill_value=0)
        rhh_pct = (rhh["PitchType"].value_counts(normalize=True) * 100).reindex(all_types, fill_value=0)

        tick_max = 100

        traces = []
        for pitch in all_types:
            color = pitch_colors_dict.get(pitch, "#9C8975")
            lv = lhh_pct[pitch]
            rv = rhh_pct[pitch]

            # LHH — negative x
            traces.append(go.Bar(
                name=pitch,
                y=[pitch],
                x=[-lv],
                orientation="h",
                marker_color=color,
                marker_opacity=0.92,
                text=[f"{lv:.1f}%"] if lv > 0 else [""],
                textposition="outside",
                textfont=dict(color="#E8E8E8", size=11),
                hovertemplate=f"<b>{pitch}</b><br>vs LHH: {lv:.1f}%<extra></extra>",
                showlegend=False,
                cliponaxis=False,
            ))
            # RHH — positive x
            traces.append(go.Bar(
                name=pitch,
                y=[pitch],
                x=[rv],
                orientation="h",
                marker_color=color,
                marker_opacity=0.92,
                text=[f"{rv:.1f}%"] if rv > 0 else [""],
                textposition="outside",
                textfont=dict(color="#E8E8E8", size=11),
                hovertemplate=f"<b>{pitch}</b><br>vs RHH: {rv:.1f}%<extra></extra>",
                showlegend=False,
                cliponaxis=False,
            ))

        # Legend traces (one per pitch type, colored)
        for pitch in all_types:
            color = pitch_colors_dict.get(pitch, "#9C8975")
            traces.append(go.Bar(
                name=pitch,
                y=[None], x=[None],
                orientation="h",
                marker_color=color,
                showlegend=True,
            ))

        tick_vals = list(range(-tick_max, tick_max + 1, 10))
        tick_text = [f"{abs(v)}%" for v in tick_vals]

        chart_height = max(260, len(all_types) * 58 + 100)

        fig = go.Figure(traces)
        fig.update_layout(
            barmode="overlay",
            plot_bgcolor="#1A1A1A",
            paper_bgcolor="#1A1A1A",
            font=dict(family="Barlow, sans-serif", color="#E8E8E8"),
            title=dict(
                text="Pitch Usage by Batter Hand",
                font=dict(color="#FDBB30", size=14, family="Barlow Condensed, sans-serif"),
                x=0.5, xanchor="center",
            ),
            xaxis=dict(
                range=[-tick_max - 5, tick_max + 5],
                tickvals=tick_vals,
                ticktext=tick_text,
                tickfont=dict(color="#999999", size=10),
                gridcolor="#3A3A3A",
                gridwidth=0.5,
                zeroline=True,
                zerolinecolor="#E8E8E8",
                zerolinewidth=1.5,
                showline=False,
                title=dict(
                    text=f"<i>← vs LHH ({n_lhh})</i>   Usage %   <i>vs RHH ({n_rhh}) →</i>",
                    font=dict(color="#FDBB30", size=11),
                ),
            ),
            yaxis=dict(
                tickfont=dict(color="#E8E8E8", size=11),
                gridcolor="#2C2C2C",
                showline=False,
                categoryorder="array",
                categoryarray=list(reversed(all_types)),
            ),
            legend=dict(
                orientation="h",
                yanchor="bottom", y=1.02,
                xanchor="center", x=0.5,
                font=dict(color="#E8E8E8", size=10),
                bgcolor="rgba(0,0,0,0)",
            ),
            margin=dict(l=20, r=20, t=60, b=50),
            height=chart_height,
        )

        html = fig.to_html(full_html=False, include_plotlyjs=False, config={"displayModeBar": False})
        return ui.HTML(html)

    # Table outputs
    @output
    @render.ui
    def everything_summary_stats_table():  # ADD THIS
        return create_summary_stats_table()
    @output
    @render.ui
    def everything_pitch_metrics_table():
        return create_pitch_metrics_table()

    @output
    @render.ui
    def everything_pitch_stats_table():
        return create_pitch_stats_table()

    @output
    @render.ui
    def data_pitch_metrics_table():
        return create_pitch_metrics_table()

    @output
    @render.ui
    def data_pitch_stats_table():
        return create_pitch_stats_table()

    @output
    @render.ui
    def leaderboard_metrics_table():
        return create_leaderboard_metrics_table()

    @output
    @render.ui
    def leaderboard_stats_table():
        return create_leaderboard_stats_table()

    # Butterfly usage chart outputs
    @output
    @render.ui
    def everything_usage_by_hand_plot():
        return create_usage_by_hand_plot()

    @output
    @render.ui
    def plots_usage_by_hand_plot():
        return create_usage_by_hand_plot()

    # Plot outputs - Everything tab
    @output
    @render.ui
    def everything_movement_plot():
        return create_plot("movement")

    @output
    @render.ui
    def everything_release_plot():
        return create_plot("release")

    @output
    @render.ui
    def everything_velocity_plot():
        return create_plot("velocity")

    @output
    @render.ui
    def everything_location_plot():
        return create_plot("location", "Pitch Locations")

    @output
    @render.ui
    def everything_strike_swinging_plot():
        return create_plot("strike_swinging", "Strike Swinging Locations", ["StrikeSwinging"])

    @output
    @render.ui
    def everything_chase_plot():
        return create_plot("chase", "Chase Pitch Locations")

    @output
    @render.ui
    def everything_called_strike_plot():
        return create_plot("called_strike", "Called Strike Locations", ["StrikeCalled"])

    @output
    @render.ui
    def everything_called_ball_plot():
        return create_plot("called_ball", "Called Ball Locations", ["BallCalled"])

    @output
    @render.ui
    def everything_arm_angle_plot():
        return create_plot("arm_angle")

    # Plot outputs - Data tab
    @output
    @render.ui
    def data_movement_plot():
        return create_plot("movement")

    @output
    @render.ui
    def data_release_plot():
        return create_plot("release")

    # Plot outputs - Plots tab
    @output
    @render.ui
    def plots_velocity_plot():
        return create_plot("velocity")

    @output
    @render.ui
    def plots_location_plot():
        return create_plot("location", "Pitch Locations")

    @output
    @render.ui
    def plots_strike_swinging_plot():
        return create_plot("strike_swinging", "Strike Swinging Locations", ["StrikeSwinging"])

    @output
    @render.ui
    def plots_chase_plot():
        return create_plot("chase", "Chase Pitch Locations")

    @output
    @render.ui
    def plots_called_strike_plot():
        return create_plot("called_strike", "Called Strike Locations", ["StrikeCalled"])

    @output
    @render.ui
    def plots_called_ball_plot():
        return create_plot("called_ball", "Called Ball Locations", ["BallCalled"])

    # Tunneling tab outputs
    @output
    @render.ui
    def tunneling_release_angles_plot():
        return create_tunneling_plot("release_angles")

    @output
    @render.ui
    def tunneling_metrics_table():
        return create_tunneling_metrics_table()

    @render.download(filename="pitcher_report.png")
    def download_report():
        data = filtered_data()
        view_mode = input.view_mode()

        if view_mode:
            display_name = "KEN_OWL Team"
        else:
            pitcher = input.pitcher_id()
            if not pitcher:
                return None
            display_name = pitcher

        if data.empty:
            return None

        grouped = data.groupby("PitchType")
        metrics = grouped.agg(
            AvgVelo=("RelSpeed", "mean"),
            InducedVertBreak=("InducedVertBreak", "mean"),
            HorzBreak=("HorzBreak", "mean"),
            SpinRate=("SpinRate", "mean"),
            RelHeight=("RelHeight", "mean"),
            RelSide=("RelSide", "mean"),
            Extension=("Extension", "mean"),
            VertApprAngle=("VertApprAngle", "mean"),
            HorzApprAngle=("HorzApprAngle", "mean"),
            ExitSpeed=("ExitSpeed", "mean"),
            Angle=("Angle", "mean")
        ).round(1)

        # Add Tilt if available
        if "Tilt" in data.columns and not data["Tilt"].isna().all():
            tilt_stats = grouped["Tilt"].mean().round(1)
            metrics["Tilt"] = tilt_stats

        metrics["MaxVelo"] = grouped["RelSpeed"].max().round(1)

        if "arm_angle" in data.columns:
            metrics["ArmAngle"] = (90 - grouped["arm_angle"].mean()).round(1)

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.axis("off")
        table = ax.table(cellText=metrics.values, colLabels=metrics.columns,
                         cellLoc="center", loc="center")
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1, 1.5)

        plt.suptitle(f"{display_name}: Pitch Metrics", fontsize=14, y=0.95)

        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", dpi=100)
        buf.seek(0)
        plt.close(fig)

        return {
            "content": buf.getvalue(),
            "filename": f"{display_name.replace(' ', '_')}_metrics_table.png",
            "media_type": "image/png"
        }


app = App(app_ui, server)