# app.py
from shiny import App, ui, render, reactive, session
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os
import glob
from scipy.ndimage import gaussian_filter
from matplotlib.patches import Rectangle
import matplotlib.patches as patches

# Set matplotlib style for better aesthetics
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")

# Define pitch color mapping with more vibrant colors
pitch_colors = {
    "Fastball": '#FF1744',
    "Four-Seam": '#FF1744',
    "Sinker": "#AD1457",
    "Slider": '#00E676',
    "Sweeper": "#00BCD4",
    "Curveball": '#3F51B5',
    "ChangeUp": '#FF9800',
    "Splitter": '#8BC34A',
    "Cutter": "#E91E63",
    "Undefined": '#795548',
    "PitchOut": '#424242'
}

# Load all CSV files from the TrackmanCSV's folder
csv_folder = "TrackmanCSV's"
csv_paths = glob.glob(os.path.join(csv_folder, "*.csv"))
if not csv_paths:
    raise RuntimeError(f"No CSV files found in '{csv_folder}' folder.")

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Same as before: add all the indicator columns to the raw DataFrame.
    """
    df = df.copy()

    # Detect possible column names
    plate_side_col = None
    plate_height_col = None
    balls_col = None
    strikes_col = None
    for col in df.columns:
        low = col.lower()
        if "plateside" in low or ("plateloc" in low and "side" in low):
            plate_side_col = col
        if "plateheight" in low or ("plateloc" in low and "height" in low):
            plate_height_col = col
        if low in ("balls", "ball"):
            balls_col = col
        if low in ("strikes", "strike"):
            strikes_col = col

    # Convert numeric columns
    for col in (plate_side_col, plate_height_col, balls_col, strikes_col):
        if col and col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Standardize column names
    if plate_side_col and plate_side_col != "PlateLocSide":
        df["PlateLocSide"] = df[plate_side_col]
    if plate_height_col and plate_height_col != "PlateLocHeight":
        df["PlateLocHeight"] = df[plate_height_col]
    if balls_col and balls_col != "Balls":
        df["Balls"] = df[balls_col]
    if strikes_col and strikes_col != "Strikes":
        df["Strikes"] = df[strikes_col]

    # Ensure required columns exist
    for required in ("Balls", "Strikes", "PitchCall"):
        if required not in df.columns:
            df[required] = 0 if required in ("Balls", "Strikes") else "Unknown"

    balls_0 = df["Balls"] == 0
    balls_1 = df["Balls"] == 1
    strikes_0 = df["Strikes"] == 0
    strikes_1 = df["Strikes"] == 1

    # EarlyIndicator
    df["EarlyIndicator"] = np.where(
        ((balls_0 & strikes_0 & (df["PitchCall"] == "InPlay"))
         | (balls_1 & strikes_0 & (df["PitchCall"] == "InPlay"))
         | (balls_0 & strikes_1 & (df["PitchCall"] == "InPlay"))
         | (balls_1 & strikes_1 & (df["PitchCall"] == "InPlay"))),
        1, 0
    )

    # AheadIndicator
    df["AheadIndicator"] = np.where(
        (((balls_0 & strikes_1) | (balls_1 & strikes_1))
         & df["PitchCall"].isin(["StrikeCalled", "StrikeSwinging", "FoulBall"])),
        1, 0
    )

    # Zone indicators
    if "PlateLocSide" in df.columns and "PlateLocHeight" in df.columns:
        in_side = df["PlateLocSide"].between(-0.8333, 0.8333)
        in_height = df["PlateLocHeight"].between(1.5, 3.37467)
        df["StrikeZoneIndicator"] = np.where(in_side & in_height, 1, 0)

        edge_h = (
            df["PlateLocHeight"].between(14 / 12, 22 / 12)
            | df["PlateLocHeight"].between(38 / 12, 46 / 12)
        )
        df["EdgeHeightIndicator"] = edge_h.astype(int)

        df["EdgeZoneHtIndicator"] = df["PlateLocHeight"].between(16 / 12, 45.2 / 12).astype(int)
        df["EdgeZoneWIndicator"] = df["PlateLocSide"].between(-13.4 / 12, 13.4 / 12).astype(int)

        edge_w = (
            df["PlateLocSide"].between(-13.3 / 12, -6.7 / 12)
            | df["PlateLocSide"].between(6.7 / 12, 13.3 / 12)
        )
        df["EdgeWidthIndicator"] = edge_w.astype(int)

        df["HeartIndicator"] = np.where(
            df["PlateLocSide"].between(-0.5583, 0.5583)
            & df["PlateLocHeight"].between(1.83, 3.5),
            1, 0
        )
    else:
        for col in (
            "StrikeZoneIndicator", "EdgeHeightIndicator", "EdgeZoneHtIndicator",
            "EdgeZoneWIndicator", "EdgeWidthIndicator", "HeartIndicator"
        ):
            df[col] = 0

    # Strike/swing indicators
    df["StrikeIndicator"] = df["PitchCall"].isin(
        ["StrikeSwinging", "StrikeCalled", "FoulBallNot", "InPlay"]
    ).astype(int)
    df["WhiffIndicator"] = (df["PitchCall"] == "StrikeSwinging").astype(int)
    df["SwingIndicator"] = df["PitchCall"].isin(
        ["StrikeSwinging", "FoulBall", "InPlay"]
    ).astype(int)

    # Batter side
    if "BatterSide" in df.columns:
        df["LHHindicator"] = (df["BatterSide"] == "Left").astype(int)
        df["RHHindicator"] = (df["BatterSide"] == "Right").astype(int)
    else:
        df["LHHindicator"] = 0
        df["RHHindicator"] = 0

    # At-bat results
    if "PlayResult" in df.columns and "KorBB" in df.columns:
        df["ABindicator"] = (
            df["PlayResult"].isin(
                ["Error", "FieldersChoice", "Out", "Single", "Double", "Triple", "Homerun"]
            ) | (df["KorBB"] == "Strikeout")
        ).astype(int)
        df["HitIndicator"] = df["PlayResult"].isin(
            ["Single", "Double", "Triple", "Homerun"]
        ).astype(int)
    else:
        df["ABindicator"] = 0
        df["HitIndicator"] = 0

    # First pitch
    df["FPindicator"] = (balls_0 & strikes_0).astype(int)

    # Plate appearance
    if "KorBB" in df.columns:
        df["PAindicator"] = (
            df["PitchCall"].isin(["InPlay", "HitByPitch", "CatchersInterference"])
            | df["KorBB"].isin(["Walk", "Strikeout"])
        ).astype(int)
    else:
        df["PAindicator"] = df["PitchCall"].isin(
            ["InPlay", "HitByPitch", "CatchersInterference"]
        ).astype(int)

    # Lead off
    if "PAofInning" in df.columns:
        df["LeadOffIndicator"] = (
            (df["PAofInning"] == 1) | (df["PitchCall"] == "HitByPitch")
        ).astype(int)
    else:
        df["LeadOffIndicator"] = 0

    # HBP and Walk
    df["HBPIndicator"] = (df["PitchCall"] == "HitByPitch").astype(int)
    if "KorBB" in df.columns:
        df["WalkIndicator"] = (df["KorBB"] == "Walk").astype(int)
    else:
        df["WalkIndicator"] = 0

    # Stolen and lost strikes
    if "PlateLocSide" in df.columns and "PlateLocHeight" in df.columns:
        outside = (
            (df["PlateLocHeight"] > 3.37467)
            | (df["PlateLocHeight"] < 1.5)
            | (df["PlateLocSide"] < -0.83083)
            | (df["PlateLocSide"] > 0.83083)
        )
        df["StolenStrike"] = (
            (df["PitchCall"] == "StrikeCalled") & outside
        ).astype(int)

        inside = (
            (df["PlateLocHeight"] < 3.37467)
            & (df["PlateLocHeight"] > 1.5)
            & (df["PlateLocSide"] > -0.83083)
            & (df["PlateLocSide"] < 0.83083)
        )
        df["StrikeLost"] = (
            (df["PitchCall"] == "BallCalled") & inside
        ).astype(int)
    else:
        df["StolenStrike"] = 0
        df["StrikeLost"] = 0

    # Edge indicator
    if "EdgeHeightIndicator" in df.columns and "EdgeZoneWIndicator" in df.columns:
        df["EdgeIndicator"] = (
            ((df["EdgeHeightIndicator"] == 1) & (df["EdgeZoneWIndicator"] == 1))
            | ((df["EdgeWidthIndicator"] == 1) & (df["EdgeZoneHtIndicator"] == 1))
        ).astype(int)
    else:
        df["EdgeIndicator"] = 0

    # Quality pitch
    if "StrikeZoneIndicator" in df.columns and "EdgeIndicator" in df.columns:
        df["QualityPitchIndicator"] = (
            (df["StrikeZoneIndicator"] == 1) | (df["EdgeIndicator"] == 1)
        ).astype(int)
    else:
        df["QualityPitchIndicator"] = 0

    # First-pitch strike
    df["FPSindicator"] = (
        df["PitchCall"].isin(["StrikeCalled", "StrikeSwinging", "FoulBall", "InPlay"])
        & (df["FPindicator"] == 1)
    ).astype(int)

    # Outs
    if "PlayResult" in df.columns and "KorBB" in df.columns:
        df["OutIndicator"] = (
            (df["PlayResult"].isin(["Out", "FieldersChoice"]) | (df["KorBB"] == "Strikeout"))
            & (df["HBPIndicator"] == 0)
        ).astype(int)
    else:
        df["OutIndicator"] = 0

    # Lead-off out
    df["LOOindicator"] = (
        (df["LeadOffIndicator"] == 1) & (df["OutIndicator"] == 1)
    ).astype(int)

    # Replace undefined PlayResult
    if "PlayResult" in df.columns:
        df["PlayResult"] = df["PlayResult"].fillna(df["PitchCall"])
        df.loc[df["PlayResult"] == "Undefined", "PlayResult"] = df.loc[
            df["PlayResult"] == "Undefined", "PitchCall"
        ]

    return df


def create_strike_zone_plot(df: pd.DataFrame, title: str, stolen: bool = True, show_heatmap: bool = True, show_dots: bool = True):
    """Create an enhanced strike zone visualization with better aesthetics."""
    # Create figure with dark background
    fig = plt.figure(figsize=(14, 12), facecolor='#1e1e1e')
    ax = fig.add_subplot(111, facecolor='#2d2d2d')
    
    # Enhanced strike zone with gradient effect
    strike_zone = Rectangle(
        (-0.83, 1.5), 1.66, 1.87,
        linewidth=3, edgecolor='#FF6B6B', facecolor='none',
        linestyle='--', alpha=0.8
    )
    ax.add_patch(strike_zone)
    
    # Add strike zone shadow for depth
    shadow_zone = Rectangle(
        (-0.825, 1.495), 1.65, 1.86,
        linewidth=1, edgecolor='#333333', facecolor='none',
        alpha=0.3
    )
    ax.add_patch(shadow_zone)

    # Enhanced home plate with better styling
    plate_x = [-0.708, 0.708, 0.708, 0, -0.708, -0.708]
    plate_y = [0.15, 0.15, 0.3, 0.5, 0.3, 0.15]
    ax.plot(plate_x, plate_y, color='white', linewidth=3, alpha=0.9)
    ax.fill(plate_x, plate_y, color='#f0f0f0', alpha=0.3)

    # Add batter's boxes for context
    # Left batter's box
    left_box = Rectangle((-1.2, -0.1), 0.4, 1.2, 
                        linewidth=2, edgecolor='#888888', 
                        facecolor='none', alpha=0.5)
    ax.add_patch(left_box)
    
    # Right batter's box
    right_box = Rectangle((0.8, -0.1), 0.4, 1.2, 
                         linewidth=2, edgecolor='#888888', 
                         facecolor='none', alpha=0.5)
    ax.add_patch(right_box)

    # Determine which column holds the pitch type
    pitch_type_col = next(
        (c for c in df.columns if "PitchType" in c or "TaggedPitchType" in c),
        None
    )

    if pitch_type_col is None or "PlateLocSide" not in df.columns or "PlateLocHeight" not in df.columns:
        ax.text(
            0.5, 0.5, f"No data available for {title}",
            ha='center', va='center', transform=ax.transAxes, 
            fontsize=16, color='white', fontweight='bold'
        )
        ax.set_xlim(-2.5, 2.5)
        ax.set_ylim(-0.5, 4.5)
        ax.set_title(title, fontsize=20, fontweight='bold', color='white', pad=20)
        ax.set_facecolor('#2d2d2d')
        return fig

    # Filter the appropriate points
    if stolen:
        pts = df[df["StolenStrike"] == 1] if "StolenStrike" in df.columns else pd.DataFrame()
        heatmap_color = 'Reds'
    else:
        pts = df[df["StrikeLost"] == 1] if "StrikeLost" in df.columns else pd.DataFrame()
        heatmap_color = 'Blues'

    if not pts.empty:
        # Create enhanced heatmap
        if show_heatmap:
            x = pts["PlateLocSide"]
            y = pts["PlateLocHeight"]
            
            # Create high-resolution histogram
            h, xedges, yedges = np.histogram2d(x, y, bins=120, range=[[-2.5, 2.5], [-0.5, 4.5]])
            
            # Apply stronger smoothing
            h = gaussian_filter(h, sigma=3.0)
            
            # Create the heatmap with enhanced styling
            im = ax.imshow(
                h.T,
                origin='lower',
                extent=[-2.5, 2.5, -0.5, 4.5],
                aspect='auto',
                cmap=heatmap_color,
                alpha=0.7,
                interpolation='bilinear'
            )
            
            # Add colorbar with custom styling
            cbar = plt.colorbar(im, ax=ax, shrink=0.8, aspect=20)
            cbar.ax.tick_params(colors='white', labelsize=10)
            cbar.set_label('Pitch Density', color='white', fontsize=12, fontweight='bold')
            cbar.ax.yaxis.set_label_position('left')
        
        # Add enhanced pitch type points
        if show_dots:
            pitch_counts = {}
            for ptype in pts[pitch_type_col].dropna().unique():
                subset = pts[pts[pitch_type_col] == ptype].dropna(subset=["PlateLocSide", "PlateLocHeight"])
                if not subset.empty:
                    color = pitch_colors.get(ptype, "#795548")
                    scatter = ax.scatter(
                        subset["PlateLocSide"], subset["PlateLocHeight"],
                        c=color, s=100, alpha=0.9, 
                        edgecolors="white", linewidth=1.5, 
                        label=f"{ptype} ({len(subset)})",
                        zorder=10
                    )
                    pitch_counts[ptype] = len(subset)

    # Enhanced styling
    ax.set_xlim(-2.5, 2.5)
    ax.set_ylim(-0.5, 4.5)
    ax.set_aspect("equal")
    
    # Enhanced title with subtitle
    count = len(pts) if not pts.empty else 0
    subtitle = f"Total Pitches: {count}"
    ax.set_title(f"{title}\n{subtitle}", fontsize=20, fontweight="bold", 
                color='white', pad=25)
    
    # Remove ticks and add grid
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(True, alpha=0.2, color='white')
    
    # Enhanced legend
    if not pts.empty and show_dots:
        legend = ax.legend(bbox_to_anchor=(1.15, 1), loc="upper left", 
                          fontsize=11, frameon=True, fancybox=True, 
                          shadow=True, framealpha=0.9)
        legend.get_frame().set_facecolor('#3d3d3d')
        for text in legend.get_texts():
            text.set_color('white')
    
    # Adjust layout
    fig.subplots_adjust(left=0.1, right=0.85, top=0.9, bottom=0.1)
    
    return fig


def create_distribution_plot(data, title, xlabel, color, bins=15):
    """Create enhanced distribution plots for throw analysis."""
    fig, ax = plt.subplots(figsize=(10, 6), facecolor='#1e1e1e')
    ax.set_facecolor('#2d2d2d')
    
    if data.empty:
        ax.text(0.5, 0.5, f"No {xlabel.lower()} data available",
                ha="center", va="center", transform=ax.transAxes, 
                fontsize=16, color='white', fontweight='bold')
        ax.set_title(title, fontsize=18, fontweight="bold", color='white', pad=20)
        return fig

    # Create histogram with enhanced styling
    n, bins_edges, patches = ax.hist(data.dropna(), bins=bins, color=color, 
                                   alpha=0.8, edgecolor='white', linewidth=1.5)
    
    # Color gradient for bars
    for i, patch in enumerate(patches):
        patch.set_facecolor(plt.cm.viridis(i / len(patches)))
    
    # Add statistics text
    mean_val = data.mean()
    median_val = data.median()
    std_val = data.std()
    
    stats_text = f"Mean: {mean_val:.2f}\nMedian: {median_val:.2f}\nStd: {std_val:.2f}"
    ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, 
            verticalalignment='top', fontsize=12, color='white',
            bbox=dict(boxstyle="round,pad=0.3", facecolor='#3d3d3d', alpha=0.8))
    
    # Enhanced styling
    ax.set_title(title, fontsize=18, fontweight="bold", color='white', pad=20)
    ax.set_xlabel(xlabel, fontsize=14, color='white', fontweight='bold')
    ax.set_ylabel("Frequency", fontsize=14, color='white', fontweight='bold')
    
    # Style the axes
    ax.tick_params(colors='white', labelsize=12)
    ax.spines['bottom'].set_color('white')
    ax.spines['top'].set_color('white')
    ax.spines['right'].set_color('white')
    ax.spines['left'].set_color('white')
    
    # Add grid
    ax.grid(True, alpha=0.3, color='white')
    
    plt.tight_layout()
    return fig


# Enhanced UI with better styling
app_ui = ui.page_fluid(
    # Add custom CSS for better styling
    ui.tags.head(
        ui.tags.style("""
            body { background-color: #f8f9fa; }
            .sidebar { background-color: #343a40 !important; color: white; }
            .sidebar h4 { color: #17a2b8; }
            .card { box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); border-radius: 8px; }
            .nav-tabs .nav-link.active { background-color: #007bff; color: white; }
            .btn-primary { background-color: #007bff; border-color: #007bff; }
            .table-responsive { border-radius: 8px; overflow: hidden; }
        """)
    ),
    ui.layout_sidebar(
        ui.sidebar(
            ui.div(
                ui.h4("🔍 Filter Options", style="color: #17a2b8; margin-bottom: 20px;"),
                ui.input_date_range(
                    "date_range",
                    "Select Date Range",
                    start=None,
                    end=None
                ),
                ui.input_select(
                    "catcher",
                    "Catcher",
                    choices=[],
                    multiple=False,
                ),
                ui.hr(style="border-color: #6c757d;"),
                ui.h4("📊 Plot Options", style="color: #17a2b8; margin-bottom: 20px;"),
                ui.input_switch("show_heatmap", "Show Heatmap", value=True),
                ui.input_switch("show_dots", "Show Individual Pitches", value=True),
                style="padding: 20px;"
            ),
            width=300,
        ),
        ui.div(
            ui.div(
                ui.h2("⚾ KSU Baseball Analytics Dashboard", 
                     style="color: #343a40; text-align: center; margin-bottom: 30px;"),
                ui.div(
                    ui.h4("📈 Game Summary"),
                    ui.div(
                        ui.output_text("ksu_summary_text"),
                        style="font-size: 20px; font-weight: bold; margin: 15px 0; "
                              "padding: 15px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); "
                              "color: white; border-radius: 8px; text-align: center;"
                    ),
                    ui.div(
                        ui.input_action_button("print_button", "🖨️ Generate Report", 
                                             class_="btn-primary btn-lg",
                                             style="margin: 10px 0;"),
                        style="text-align: center;"
                    ),
                    ui.div(
                        ui.output_table("ksu_summary_table"),
                        class_="table-responsive",
                        style="margin: 20px 0;"
                    ),
                    class_="card",
                    style="padding: 20px; margin-bottom: 30px; background-color: white;"
                ),
                ui.h3("📊 Analysis Visualizations", style="color: #343a40; margin-bottom: 20px;"),
                ui.navset_tab(
                    ui.nav_panel(
                        "🎯 Strike Zone Analysis",
                        ui.div(
                            ui.layout_columns(
                                ui.div(
                                    ui.output_plot("stolen_strikes_plot"),
                                    class_="card",
                                    style="padding: 15px; margin: 10px; background-color: white;"
                                ),
                                ui.div(
                                    ui.output_plot("lost_strikes_plot"),
                                    class_="card",
                                    style="padding: 15px; margin: 10px; background-color: white;"
                                ),
                                fill=False
                            ),
                            style="margin-top: 20px;"
                        )
                    ),
                    ui.nav_panel(
                        "🚀 Throw Analysis",
                        ui.div(
                            ui.div(
                                ui.h4("📊 Pop Time Distribution", style="color: #343a40;"),
                                ui.output_plot("pop_time_plot"),
                                class_="card",
                                style="padding: 20px; margin: 15px 0; background-color: white;"
                            ),
                            ui.div(
                                ui.h4("🎯 Throw Speed Distribution", style="color: #343a40;"),
                                ui.output_plot("throw_speed_plot"),
                                class_="card",
                                style="padding: 20px; margin: 15px 0; background-color: white;"
                            ),
                            ui.div(
                                ui.h4("⏱️ Detailed Pop Time Data", style="color: #343a40;"),
                                ui.output_table("pop_time_table"),
                                class_="card table-responsive",
                                style="padding: 20px; margin: 15px 0; background-color: white;"
                            ),
                            style="margin-top: 20px;"
                        )
                    ),
                ),
                style="max-width: 1400px; margin: 0 auto;"
            )
        )
    )
)


def server(input, output, session):
    @reactive.Calc
    def raw_data():
        """Read and combine all CSV files from the TrackmanCSV's folder"""
        try:
            dfs = []
            for file_path in csv_paths:
                try:
                    df = pd.read_csv(file_path)
                except UnicodeDecodeError:
                    df = pd.read_csv(file_path, encoding="latin-1")
                except Exception:
                    df = pd.read_csv(file_path, sep=None, engine="python")
                
                # Add filename as a column to track source
                df['SourceFile'] = os.path.basename(file_path)
                dfs.append(df)
            
            if not dfs:
                return None
                
            # Combine all dataframes
            combined_df = pd.concat(dfs, ignore_index=True)
            
            # Convert date column if it exists
            if "Date" in combined_df.columns:
                combined_df["Date"] = pd.to_datetime(combined_df["Date"], errors='coerce')

            # Filter for KEN_OWL team
            team_col = next(
                (c for c in combined_df.columns if "PitcherTeam" in c or "pitcher_team" in c.lower() or "team" in c.lower()),
                None
            )
            if team_col:
                combined_df = combined_df[combined_df[team_col] == "KEN_OWL"]

            combined_df = compute_indicators(combined_df)
            return combined_df

        except Exception as e:
            print(f"Error loading data: {str(e)}")
            return None

    @reactive.Calc
    def filtered_data():
        """Apply all filters to the data"""
        df = raw_data()
        if df is None:
            return None

        # Apply date filter if dates are selected
        date_range = input.date_range()
        if date_range and "Date" in df.columns:
            start_date = pd.to_datetime(date_range[0])
            end_date = pd.to_datetime(date_range[1])
            df = df[(df["Date"] >= start_date) & (df["Date"] <= end_date)]

        # Apply catcher filter
        catcher = input.catcher()
        if catcher:
            catcher_col = next(
                (c for c in df.columns if "Catcher" in c or "catcher" in c.lower()),
                None
            )
            if catcher_col:
                df = df[df[catcher_col] == catcher]

        return df

    @reactive.Effect
    def update_catcher_choices():
        df = raw_data()
        if df is None:
            return
        catcher_col = next(
            (c for c in df.columns if "Catcher" in c or "catcher" in c.lower()),
            None
        )
        if catcher_col is None:
            return
        catchers = sorted(df[catcher_col].dropna().astype(str).unique())
        ui.update_select("catcher", choices=catchers, session=session)

    @reactive.Calc
    def ksu_summary_df():
        df = filtered_data()
        if df is None or df.empty:
            return pd.DataFrame({
                "KSU Strikes Stolen": [0],
                "KSU Strikes Lost": [0],
                "KSU Game +/-": [0]
            })
        stolen = int(df["StolenStrike"].sum()) if "StolenStrike" in df.columns else 0
        lost = int(df["StrikeLost"].sum()) if "StrikeLost" in df.columns else 0
        net = stolen - lost
        return pd.DataFrame({
            "KSU Strikes Stolen": [stolen],
            "KSU Strikes Lost": [lost],
            "KSU Game +/-": [net]
        })

    @output
    @render.text
    def ksu_summary_text():
        df = ksu_summary_df()
        if df.empty:
            return "Stolen: 0   |   Lost: 0   |   Net: 0"
        stolen = int(df["KSU Strikes Stolen"].iloc[0])
        lost = int(df["KSU Strikes Lost"].iloc[0])
        net = int(df["KSU Game +/-"].iloc[0])
        return f"Stolen: {stolen}   |   Lost: {lost}   |   Net: {net}"

    @output
    @render.table
    def ksu_summary_table():
        return ksu_summary_df()

    @output
    @render.plot
    def stolen_strikes_plot():
        df = filtered_data()
        if df is None:
            return create_strike_zone_plot(pd.DataFrame(), "Strikes Stolen")
        df_ss = df[df["StolenStrike"] == 1] if "StolenStrike" in df.columns else pd.DataFrame()
        return create_strike_zone_plot(
            df_ss, 
            "Strikes Stolen", 
            stolen=True,
            show_heatmap=input.show_heatmap(),
            show_dots=input.show_dots()
        )

    @output
    @render.plot
    def lost_strikes_plot():
        df = filtered_data()
        if df is None:
            return create_strike_zone_plot(pd.DataFrame(), "Strikes Lost", stolen=False)
        df_ls = df[df["StrikeLost"] == 1] if "StrikeLost" in df.columns else pd.DataFrame()
        return create_strike_zone_plot(
            df_ls, 
            "Strikes Lost", 
            stolen=False,
            show_heatmap=input.show_heatmap(),
            show_dots=input.show_dots()
        )

    @reactive.Effect
    def _():
        # Force plot updates when switches change
        input.show_heatmap()
        input.show_dots()

    @reactive.Calc
    def throwlog_df():
        """Filter by selected catcher, then keep only rows with a non-null PopTime."""
        df = filtered_data()
        if df is None or "PopTime" not in df.columns:
            return pd.DataFrame()
        df2 = df[df["PopTime"].notna()].copy()
        needed = [
            c
            for c in ["PitchNo", "Pitcher", "Catcher", "ThrowSpeed", "PopTime"]
            if c in df2.columns
        ]
        return df2[needed]

    @output
    @render.plot
    def pop_time_plot():
        df = throwlog_df()
        if df.empty or "PopTime" not in df.columns:
            return create_distribution_plot(pd.Series(), "Pop Time Distribution", 
                                          "Pop Time (seconds)", "#3F51B5")
        
        return create_distribution_plot(df["PopTime"], "Pop Time Distribution", 
                                      "Pop Time (seconds)", "#3F51B5")

    @output
    @render.plot
    def throw_speed_plot():
        df = throwlog_df()
        if df.empty or "ThrowSpeed" not in df.columns:
            return create_distribution_plot(pd.Series(), "Throw Speed Distribution", 
                                          "Throw Speed (mph)", "#FF9800")
        
        return create_distribution_plot(df["ThrowSpeed"], "Throw Speed Distribution", 
                                      "Throw Speed (mph)", "#FF9800")

    @output
    @render.table
    def pop_time_table():
        """Show a table of PopTime values for every pitch (filtered by selected catcher)."""
        df = throwlog_df()
        if df.empty or "PopTime" not in df.columns:
            return pd.DataFrame({"Message": ["No PopTime data available"]})
        
        # Enhanced table with better formatting
        cols = [c for c in ["PitchNo", "Catcher", "PopTime", "ThrowSpeed"] if c in df.columns]
        result_df = df[cols].copy()
        
        # Format the columns for better display
        if "PopTime" in result_df.columns:
            result_df["Pop Time (sec)"] = result_df["PopTime"].round(3)
            result_df = result_df.drop("PopTime", axis=1)
        
        if "ThrowSpeed" in result_df.columns:
            result_df["Throw Speed (mph)"] = result_df["ThrowSpeed"].round(1)
            result_df = result_df.drop("ThrowSpeed", axis=1)
            
        return result_df.head(20)  # Limit to first 20 rows for better display

    @reactive.Effect
    @reactive.event(input.print_button)
    def _():
        session.send_custom_message("print", {})
        print("Print button clicked")  # Debug print


app = App(app_ui, server)

if __name__ == "__main__":
    app.run()