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
from matplotlib.lines import Line2D

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


def create_combined_strike_zone_plot(df: pd.DataFrame, show_heatmap: bool = True, show_dots: bool = True):
    """Create a combined strike zone visualization showing both stolen and lost strikes."""
    # Create figure with white background - LARGE SIZE
    fig = plt.figure(figsize=(20, 16), facecolor='white')
    ax = fig.add_subplot(111, facecolor='white')
    
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
        linewidth=1, edgecolor='#cccccc', facecolor='none',
        alpha=0.3
    )
    ax.add_patch(shadow_zone)

    # Enhanced home plate with better styling
    plate_x = [-0.708, 0.708, 0.708, 0, -0.708, -0.708]
    plate_y = [0.15, 0.15, 0.3, 0.5, 0.3, 0.15]
    ax.plot(plate_x, plate_y, color='black', linewidth=3, alpha=0.9)
    ax.fill(plate_x, plate_y, color='#f0f0f0', alpha=0.3)

    # Determine which column holds the pitch type
    pitch_type_col = next(
        (c for c in df.columns if "PitchType" in c or "TaggedPitchType" in c),
        None
    )

    if pitch_type_col is None or "PlateLocSide" not in df.columns or "PlateLocHeight" not in df.columns:
        ax.text(
            0.5, 0.5, "No data available for strike zone analysis",
            ha='center', va='center', transform=ax.transAxes, 
            fontsize=16, color='black', fontweight='bold'
        )
        ax.set_xlim(-2.5, 2.5)
        ax.set_ylim(-0.5, 4.5)
        ax.set_title("Combined Strike Zone Analysis", fontsize=20, fontweight='bold', color='black', pad=20)
        ax.set_facecolor('white')
        return fig

    # Get stolen and lost strikes data
    stolen_pts = df[df["StolenStrike"] == 1] if "StolenStrike" in df.columns else pd.DataFrame()
    lost_pts = df[df["StrikeLost"] == 1] if "StrikeLost" in df.columns else pd.DataFrame()

    # Create combined heatmap if enabled
    if show_heatmap and (not stolen_pts.empty or not lost_pts.empty):
        # Create separate heatmaps for stolen (positive) and lost (negative) strikes
        if not stolen_pts.empty:
            x_stolen = stolen_pts["PlateLocSide"]
            y_stolen = stolen_pts["PlateLocHeight"]
            h_stolen, xedges, yedges = np.histogram2d(x_stolen, y_stolen, bins=200, range=[[-2.5, 2.5], [-0.5, 4.5]])
            h_stolen = gaussian_filter(h_stolen, sigma=4.0)
        else:
            h_stolen = np.zeros((200, 200))

        if not lost_pts.empty:
            x_lost = lost_pts["PlateLocSide"]
            y_lost = lost_pts["PlateLocHeight"]
            h_lost, xedges, yedges = np.histogram2d(x_lost, y_lost, bins=200, range=[[-2.5, 2.5], [-0.5, 4.5]])
            h_lost = gaussian_filter(h_lost, sigma=4.0)
        else:
            h_lost = np.zeros((200, 200))

        # Combine heatmaps: positive values for stolen strikes, negative for lost strikes
        h_combined = h_stolen - h_lost
        
        # Create the combined heatmap with red-blue diverging colormap (no colorbar)
        im = ax.imshow(
            h_combined.T,
            origin='lower',
            extent=[-2.5, 2.5, -0.5, 4.5],
            aspect='auto',
            cmap='RdBu_r',  # Red for stolen (positive), Blue for lost (negative)
            alpha=0.9,
            interpolation='bilinear',
            vmin=-np.max(np.abs(h_combined)) if np.max(np.abs(h_combined)) > 0 else -1,
            vmax=np.max(np.abs(h_combined)) if np.max(np.abs(h_combined)) > 0 else 1
        )
    
    # Add pitch type points if enabled
    if show_dots:
        # Plot stolen strikes with circle markers
        if not stolen_pts.empty:
            for ptype in stolen_pts[pitch_type_col].dropna().unique():
                subset = stolen_pts[stolen_pts[pitch_type_col] == ptype].dropna(subset=["PlateLocSide", "PlateLocHeight"])
                if not subset.empty:
                    color = pitch_colors.get(ptype, "#795548")
                    ax.scatter(
                        subset["PlateLocSide"], subset["PlateLocHeight"],
                        c=color, s=200, alpha=0.9, marker='o',
                        edgecolors="black", linewidth=2.5,
                        label=f"Stolen - {ptype} ({len(subset)})",
                        zorder=10
                    )
        
        # Plot lost strikes with square markers
        if not lost_pts.empty:
            for ptype in lost_pts[pitch_type_col].dropna().unique():
                subset = lost_pts[lost_pts[pitch_type_col] == ptype].dropna(subset=["PlateLocSide", "PlateLocHeight"])
                if not subset.empty:
                    color = pitch_colors.get(ptype, "#795548")
                    ax.scatter(
                        subset["PlateLocSide"], subset["PlateLocHeight"],
                        c=color, s=200, alpha=0.9, marker='s',
                        edgecolors="black", linewidth=2.5,
                        label=f"Lost - {ptype} ({len(subset)})",
                        zorder=10
                    )

    # Enhanced styling
    ax.set_xlim(-2.5, 2.5)
    ax.set_ylim(-0.5, 4.5)
    ax.set_aspect("equal")
    
    # Enhanced title with subtitle
    stolen_count = len(stolen_pts) if not stolen_pts.empty else 0
    lost_count = len(lost_pts) if not lost_pts.empty else 0
    net_advantage = stolen_count - lost_count
    
    subtitle = f"Stolen: {stolen_count} | Lost: {lost_count} | Net: {net_advantage:+d}"
    ax.set_title(f"Combined Strike Zone Analysis - KEN_OWL\n{subtitle}", fontsize=24, fontweight="bold", 
                color='black', pad=25)
    
    # Remove ticks and add grid
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(True, alpha=0.2, color='gray')
    
    # Enhanced legend with explanation
    if show_dots and (not stolen_pts.empty or not lost_pts.empty):
        # Add legend explanation
        legend_elements = []
        if not stolen_pts.empty or not lost_pts.empty:
            # Add custom legend entries for symbols
            legend_elements.extend([
                Line2D([0], [0], marker='o', color='w', markerfacecolor='gray', 
                       markersize=12, label='● = Stolen Strikes', markeredgecolor='black', markeredgewidth=2),
                Line2D([0], [0], marker='s', color='w', markerfacecolor='gray', 
                       markersize=12, label='■ = Lost Strikes', markeredgecolor='black', markeredgewidth=2),
                Line2D([0], [0], color='none', label='')  # Spacer
            ])
        
        # Get existing handles and labels
        handles, labels = ax.get_legend_handles_labels()
        
        # Combine custom elements with existing ones
        all_handles = legend_elements + handles
        all_labels = [elem.get_label() for elem in legend_elements] + labels
        
        legend = ax.legend(all_handles, all_labels, bbox_to_anchor=(1.05, 1), loc="upper left",
                          fontsize=9, frameon=True, fancybox=True,
                          shadow=True, framealpha=0.9, markerscale=1.0)
        legend.get_frame().set_facecolor('white')
        for text in legend.get_texts():
            text.set_color('black')
    
    # Adjust layout - more space since no colorbar
    fig.subplots_adjust(left=0.1, right=0.95, top=0.9, bottom=0.1)
    
    return fig


def create_distribution_plot(data, title, xlabel, color, bins=15):
    """Create enhanced distribution plots for throw analysis."""
    fig, ax = plt.subplots(figsize=(10, 6), facecolor='white')
    ax.set_facecolor('white')
    
    if data.empty:
        ax.text(0.5, 0.5, f"No {xlabel.lower()} data available",
                ha="center", va="center", transform=ax.transAxes, 
                fontsize=16, color='black', fontweight='bold')
        ax.set_title(title, fontsize=18, fontweight="bold", color='black', pad=20)
        return fig

    # Create histogram with enhanced styling
    n, bins_edges, patches = ax.hist(data.dropna(), bins=bins, color=color, 
                                   alpha=0.8, edgecolor='black', linewidth=1.5)
    
    # Color gradient for bars
    for i, patch in enumerate(patches):
        patch.set_facecolor(plt.cm.viridis(i / len(patches)))
    
    # Add statistics text
    mean_val = data.mean()
    median_val = data.median()
    std_val = data.std()
    
    stats_text = f"Mean: {mean_val:.2f}\nMedian: {median_val:.2f}\nStd: {std_val:.2f}"
    ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, 
            verticalalignment='top', fontsize=12, color='black',
            bbox=dict(boxstyle="round,pad=0.3", facecolor='lightgray', alpha=0.8))
    
    # Enhanced styling
    ax.set_title(title, fontsize=18, fontweight="bold", color='black', pad=20)
    ax.set_xlabel(xlabel, fontsize=14, color='black', fontweight='bold')
    ax.set_ylabel("Frequency", fontsize=14, color='black', fontweight='bold')
    
    # Style the axes
    ax.tick_params(colors='black', labelsize=12)
    ax.spines['bottom'].set_color('black')
    ax.spines['top'].set_color('black')
    ax.spines['right'].set_color('black')
    ax.spines['left'].set_color('black')
    
    # Add grid
    ax.grid(True, alpha=0.3, color='gray')
    
    plt.tight_layout()
    return fig


# Enhanced UI with KEN_OWL filter
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
                ui.div(
                    ui.h5("🥎 Catcher: KEN_OWL", style="color: #28a745; margin-bottom: 15px; font-weight: bold;"),
                    style="background-color: #d4edda; padding: 10px; border-radius: 5px; border: 1px solid #c3e6cb;"
                ),
                ui.input_date_range(
                    "date_range",
                    "Select Date Range",
                    start=None,
                    end=None
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
                ui.h2("KSU Catching Dashboard - KEN_OWL Analysis", 
                     style="color: #343a40; text-align: center; margin-bottom: 30px;"),
                ui.div(
                    ui.h3("📈 Game Performance Summary", style="color: #2c3e50; margin-bottom: 25px; text-align: center; font-weight: 700;"),
                    ui.div(
                        ui.div(
                            ui.output_text("ksu_summary_text"),
                            style="font-size: 28px; font-weight: 800; margin: 20px 0; "
                                  "padding: 25px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); "
                                  "color: white; border-radius: 12px; text-align: center; "
                                  "box-shadow: 0 8px 25px rgba(0,0,0,0.15); "
                                  "border: 2px solid rgba(255,255,255,0.1);"
                        ),
                        ui.div(
                            ui.input_action_button("print_button", "🖨️ Generate Detailed Report", 
                                                 class_="btn-primary btn-lg",
                                                 style="margin: 15px 0; padding: 12px 30px; font-size: 16px; font-weight: 600; "
                                                       "background: linear-gradient(45deg, #007bff, #0056b3); "
                                                       "border: none; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,123,255,0.3);"),
                            style="text-align: center;"
                        ),
                        ui.div(
                            ui.div(
                                ui.h5("📊 Detailed Statistics", style="color: #495057; margin-bottom: 15px; font-weight: 600;"),
                                ui.output_table("ksu_summary_table"),
                                style="background: #f8f9fa; padding: 20px; border-radius: 8px; "
                                      "border: 1px solid #dee2e6; box-shadow: 0 2px 8px rgba(0,0,0,0.08);"
                            ),
                            class_="table-responsive",
                            style="margin: 20px 0;"
                        )
                    ),
                    class_="card",
                    style="padding: 30px; margin-bottom: 40px; background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); "
                          "border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); "
                          "border: 1px solid rgba(255,255,255,0.2);"
                ),
                ui.h3("📊 Analysis Visualizations", style="color: #343a40; margin-bottom: 20px;"),
                ui.navset_tab(
                    ui.nav_panel(
                        "🎯 Strike Zone Analysis",
                        ui.div(
                            ui.div(
                                ui.output_plot("combined_strike_zone_plot", height="900px"),
                                class_="card",
                                style="padding: 25px; margin: 20px auto; background-color: white; "
                                      "border-radius: 12px; box-shadow: 0 6px 20px rgba(0,0,0,0.1); "
                                      "max-width: 1200px;"
                            ),
                            style="margin-top: 20px; text-align: center;"
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
                                ui.h4("📈 Throwing Performance Summary", style="color: #343a40;"),
                                ui.output_table("throw_summary_table"),
                                class_="card",
                                style="padding: 20px; margin: 15px 0; background-color: white;"
                            )
                        )
                    ),
                    ui.nav_panel(
                        "📊 Performance Metrics",
                        ui.div(
                            ui.div(
                                ui.h4("⚾ Pitch Type Analysis", style="color: #343a40;"),
                                ui.output_plot("pitch_type_plot"),
                                class_="card",
                                style="padding: 20px; margin: 15px 0; background-color: white;"
                            ),
                            ui.div(
                                ui.h4("📈 Performance Trends", style="color: #343a40;"),
                                ui.output_plot("performance_trends_plot"),
                                class_="card",
                                style="padding: 20px; margin: 15px 0; background-color: white;"
                            )
                        )
                    )
                )
            ),
            style="padding: 20px;"
        )
    )
)


def server(input, output, session):
    # Load and combine all CSV data
    @reactive.calc
    def load_data():
        all_data = []
        for csv_path in csv_paths:
            try:
                df = pd.read_csv(csv_path)
                df = compute_indicators(df)
                all_data.append(df)
            except Exception as e:
                print(f"Error loading {csv_path}: {e}")
        
        if all_data:
            combined_df = pd.concat(all_data, ignore_index=True)
            
            # Convert Date column to datetime if it exists
            if "Date" in combined_df.columns:
                combined_df["Date"] = pd.to_datetime(combined_df["Date"], errors='coerce')
            
            return combined_df
        else:
            return pd.DataFrame()

    # Update UI choices based on loaded data
    @reactive.effect
    def update_choices():
        df = load_data()
        
        if not df.empty:
            # Update date range
            if "Date" in df.columns and not df["Date"].isna().all():
                min_date = df["Date"].min()
                max_date = df["Date"].max()
                ui.update_date_range(
                    "date_range",
                    start=min_date,
                    end=max_date
                )

    # Filter data for KEN_OWL only
    @reactive.calc
    def filtered_data():
        df = load_data()
        
        if df.empty:
            return df
        
        # Filter for KEN_OWL catcher only
        catcher_col = next((c for c in df.columns if "catcher" in c.lower()), None)
        if catcher_col:
            df = df[df[catcher_col] == "KEN_OWL"]
        
        # Filter by date range
        if input.date_range() and "Date" in df.columns:
            start_date, end_date = input.date_range()
            if start_date and end_date:
                # Convert date objects to pandas datetime for comparison
                start_date = pd.to_datetime(start_date)
                end_date = pd.to_datetime(end_date)
                df = df[(df["Date"] >= start_date) & (df["Date"] <= end_date)]
        
        return df

    # KSU Summary Text
    @render.text
    def ksu_summary_text():
        df = filtered_data()
        if df.empty:
            return "No data available for KEN_OWL in the selected date range."
        
        total_pitches = len(df)
        stolen_strikes = df["StolenStrike"].sum() if "StolenStrike" in df.columns else 0
        lost_strikes = df["StrikeLost"].sum() if "StrikeLost" in df.columns else 0
        net_strikes = stolen_strikes - lost_strikes
        
        if total_pitches > 0:
            stolen_pct = (stolen_strikes / total_pitches) * 100
            lost_pct = (lost_strikes / total_pitches) * 100
        else:
            stolen_pct = lost_pct = 0
        
        return (f"KEN_OWL Performance - Total Pitches: {total_pitches:,} | "
                f"Stolen Strikes: {stolen_strikes} ({stolen_pct:.1f}%) | "
                f"Lost Strikes: {lost_strikes} ({lost_pct:.1f}%) | "
                f"Net Advantage: {net_strikes:+d}")

    # KSU Summary Table
    @render.table
    def ksu_summary_table():
        df = filtered_data()
        if df.empty:
            return pd.DataFrame({"Metric": ["No data"], "Value": ["available for KEN_OWL"]})
        
        # Calculate various metrics
        metrics = {}
        
        # Basic counts
        metrics["Total Pitches"] = len(df)
        metrics["Strike Zone %"] = f"{(df['StrikeZoneIndicator'].sum() / len(df) * 100):.1f}%" if "StrikeZoneIndicator" in df.columns else "N/A"
        metrics["First Pitch Strikes"] = f"{df['FPSindicator'].sum()}" if "FPSindicator" in df.columns else "N/A"
        metrics["Quality Pitches"] = f"{df['QualityPitchIndicator'].sum()}" if "QualityPitchIndicator" in df.columns else "N/A"
        
        # Swing metrics
        if "SwingIndicator" in df.columns:
            swings = df["SwingIndicator"].sum()
            whiffs = df["WhiffIndicator"].sum() if "WhiffIndicator" in df.columns else 0
            metrics["Total Swings"] = swings
            metrics["Whiff Rate"] = f"{(whiffs / swings * 100):.1f}%" if swings > 0 else "0.0%"
        
        # Convert to DataFrame
        summary_df = pd.DataFrame([
            {"Metric": k, "Value": v} for k, v in metrics.items()
        ])
        
        return summary_df

    # Combined Strike Zone Plot
    @render.plot
    def combined_strike_zone_plot():
        df = filtered_data()
        return create_combined_strike_zone_plot(
            df, 
            show_heatmap=input.show_heatmap(), 
            show_dots=input.show_dots()
        )

    # Pop Time Plot
    @render.plot
    def pop_time_plot():
        df = filtered_data()
        pop_time_col = next((c for c in df.columns if "poptime" in c.lower() or "pop_time" in c.lower()), None)
        
        if pop_time_col and pop_time_col in df.columns:
            pop_times = pd.to_numeric(df[pop_time_col], errors='coerce')
            return create_distribution_plot(
                pop_times, 
                "Pop Time Distribution - KEN_OWL", 
                "Pop Time (seconds)", 
                "#17a2b8"
            )
        else:
            fig, ax = plt.subplots(figsize=(10, 6), facecolor='white')
            ax.set_facecolor('white')
            ax.text(0.5, 0.5, "No pop time data available for KEN_OWL", 
                   ha="center", va="center", transform=ax.transAxes,
                   fontsize=16, color='black', fontweight='bold')
            ax.set_title("Pop Time Distribution - KEN_OWL", fontsize=18, fontweight="bold", color='black', pad=20)
            return fig

    # Throw Speed Plot
    @render.plot
    def throw_speed_plot():
        df = filtered_data()
        throw_speed_col = next((c for c in df.columns if "throwspeed" in c.lower() or "throw_speed" in c.lower()), None)
        
        if throw_speed_col and throw_speed_col in df.columns:
            throw_speeds = pd.to_numeric(df[throw_speed_col], errors='coerce')
            return create_distribution_plot(
                throw_speeds,
                "Throw Speed Distribution - KEN_OWL",
                "Throw Speed (mph)",
                "#28a745"
            )
        else:
            fig, ax = plt.subplots(figsize=(10, 6), facecolor='white')
            ax.set_facecolor('white')
            ax.text(0.5, 0.5, "No throw speed data available for KEN_OWL",
                   ha="center", va="center", transform=ax.transAxes,
                   fontsize=16, color='black', fontweight='bold')
            ax.set_title("Throw Speed Distribution - KEN_OWL", fontsize=18, fontweight="bold", color='black', pad=20)
            return fig

    # Throw Summary Table
    @render.table
    def throw_summary_table():
        df = filtered_data()
        if df.empty:
            return pd.DataFrame({"Metric": ["No data"], "Value": ["available for KEN_OWL"]})
        
        metrics = {}
        
        # Pop time metrics
        pop_time_col = next((c for c in df.columns if "poptime" in c.lower() or "pop_time" in c.lower()), None)
        if pop_time_col:
            pop_times = pd.to_numeric(df[pop_time_col], errors='coerce').dropna()
            if not pop_times.empty:
                metrics["Avg Pop Time"] = f"{pop_times.mean():.3f}s"
                metrics["Best Pop Time"] = f"{pop_times.min():.3f}s"
                metrics["Pop Time Std"] = f"{pop_times.std():.3f}s"
        
        # Throw speed metrics
        throw_speed_col = next((c for c in df.columns if "throwspeed" in c.lower() or "throw_speed" in c.lower()), None)
        if throw_speed_col:
            throw_speeds = pd.to_numeric(df[throw_speed_col], errors='coerce').dropna()
            if not throw_speeds.empty:
                metrics["Avg Throw Speed"] = f"{throw_speeds.mean():.1f} mph"
                metrics["Max Throw Speed"] = f"{throw_speeds.max():.1f} mph"
                metrics["Throw Speed Std"] = f"{throw_speeds.std():.1f} mph"
        
        # Convert to DataFrame
        if metrics:
            summary_df = pd.DataFrame([
                {"Metric": k, "Value": v} for k, v in metrics.items()
            ])
        else:
            summary_df = pd.DataFrame({"Metric": ["No throwing data"], "Value": ["available for KEN_OWL"]})
        
        return summary_df

    # Pitch Type Plot
    @render.plot
    def pitch_type_plot():
        df = filtered_data()
        pitch_type_col = next((c for c in df.columns if "PitchType" in c or "TaggedPitchType" in c), None)
        
        if not pitch_type_col or df.empty:
            fig, ax = plt.subplots(figsize=(10, 6), facecolor='white')
            ax.set_facecolor('white')
            ax.text(0.5, 0.5, "No pitch type data available for KEN_OWL",
                   ha="center", va="center", transform=ax.transAxes,
                   fontsize=16, color='black', fontweight='bold')
            ax.set_title("Pitch Type Distribution - KEN_OWL", fontsize=18, fontweight="bold", color='black', pad=20)
            return fig
        
        # Create pitch type distribution
        pitch_counts = df[pitch_type_col].value_counts()
        
        fig, ax = plt.subplots(figsize=(12, 8), facecolor='white')
        ax.set_facecolor('white')
        
        # Create bar plot with custom colors
        colors = [pitch_colors.get(pitch, '#795548') for pitch in pitch_counts.index]
        bars = ax.bar(pitch_counts.index, pitch_counts.values, color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)
        
        # Add value labels on bars
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + height*0.01,
                   f'{int(height)}', ha='center', va='bottom', color='black', fontweight='bold')
        
        ax.set_title("Pitch Type Distribution - KEN_OWL", fontsize=18, fontweight="bold", color='black', pad=20)
        ax.set_xlabel("Pitch Type", fontsize=14, color='black', fontweight='bold')
        ax.set_ylabel("Count", fontsize=14, color='black', fontweight='bold')
        
        # Style the axes
        ax.tick_params(colors='black', labelsize=12, rotation=45)
        ax.spines['bottom'].set_color('black')
        ax.spines['top'].set_color('black')
        ax.spines['right'].set_color('black')
        ax.spines['left'].set_color('black')
        
        # Add grid
        ax.grid(True, alpha=0.3, color='gray')
        
        plt.tight_layout()
        return fig

    # Performance Trends Plot
    @render.plot
    def performance_trends_plot():
        df = filtered_data()
        
        if df.empty or "Date" not in df.columns:
            fig, ax = plt.subplots(figsize=(12, 6), facecolor='white')
            ax.set_facecolor('white')
            ax.text(0.5, 0.5, "No date data available for trends - KEN_OWL",
                   ha="center", va="center", transform=ax.transAxes,
                   fontsize=16, color='black', fontweight='bold')
            ax.set_title("Performance Trends Over Time - KEN_OWL", fontsize=18, fontweight="bold", color='black', pad=20)
            return fig
        
        # Group by date and calculate daily metrics
        daily_stats = df.groupby('Date').agg({
            'StolenStrike': 'sum',
            'StrikeLost': 'sum',
            'QualityPitchIndicator': 'sum' if 'QualityPitchIndicator' in df.columns else 'count',
            'Date': 'count'  # Total pitches
        }).rename(columns={'Date': 'TotalPitches'})
        
        daily_stats['NetStrikes'] = daily_stats['StolenStrike'] - daily_stats['StrikeLost']
        daily_stats['QualityPct'] = (daily_stats['QualityPitchIndicator'] / daily_stats['TotalPitches'] * 100)
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), facecolor='white')
        
        # Plot 1: Net Strikes Over Time
        ax1.set_facecolor('white')
        ax1.plot(daily_stats.index, daily_stats['NetStrikes'], 
                marker='o', linewidth=2, markersize=6, color='#17a2b8')
        ax1.axhline(y=0, color='black', linestyle='--', alpha=0.5)
        ax1.set_title("Net Strikes Trend - KEN_OWL", fontsize=16, fontweight="bold", color='black')
        ax1.set_ylabel("Net Strikes", fontsize=12, color='black', fontweight='bold')
        ax1.tick_params(colors='black', labelsize=10)
        ax1.grid(True, alpha=0.3, color='gray')
        
        # Style spines
        for spine in ax1.spines.values():
            spine.set_color('black')
        
        # Plot 2: Quality Pitch Percentage Over Time
        ax2.set_facecolor('white')
        ax2.plot(daily_stats.index, daily_stats['QualityPct'], 
                marker='s', linewidth=2, markersize=6, color='#28a745')
        ax2.set_title("Quality Pitch Percentage Trend - KEN_OWL", fontsize=16, fontweight="bold", color='black')
        ax2.set_xlabel("Date", fontsize=12, color='black', fontweight='bold')
        ax2.set_ylabel("Quality Pitch %", fontsize=12, color='black', fontweight='bold')
        ax2.tick_params(colors='black', labelsize=10)
        ax2.grid(True, alpha=0.3, color='gray')
        
        # Style spines
        for spine in ax2.spines.values():
            spine.set_color('black')
        
        plt.tight_layout()
        return fig

    # Print button functionality (placeholder)
    @reactive.effect
    @reactive.event(input.print_button)
    def print_report():
        # This would generate a detailed report
        # For now, we'll just show a message
        ui.notification_show("KEN_OWL detailed report generation feature coming soon!", type="message")


# Create the app
app = App(app_ui, server)