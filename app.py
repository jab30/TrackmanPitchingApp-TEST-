# app.py
from shiny import App, ui, render, reactive, session
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

# Define pitch color mapping (unchanged)
pitch_colors = {
    "Fastball": '#ff007d',
    "Four-Seam": '#ff007d',
    "Sinker": "#98165D",
    "Slider": "#67E18D",
    "Sweeper": "#1BB999",
    "Curveball": '#3025CE',
    "ChangeUp": '#F79E70',
    "Splitter": '#90EE32',
    "Cutter": "#BE5FA0",
    "Undefined": '#9C8975',
    "PitchOut": '#472C30'
}


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


def create_strike_zone_plot(df: pd.DataFrame, title: str, stolen: bool = True):
    """Create a larger, square plot for strike zone visualization with legends on both."""
    fig, ax = plt.subplots(figsize=(8, 8))

    # Draw strike zone rectangle
    strike_zone = plt.Rectangle(
        (-0.83, 1.5), 1.66, 1.87,
        linewidth=2, edgecolor='red', facecolor='none'
    )
    ax.add_patch(strike_zone)

    # Draw home plate outline
    plate_x = [-0.708, 0.708, 0.708, 0, -0.708, -0.708]
    plate_y = [0.15, 0.15, 0.3, 0.5, 0.3, 0.15]
    ax.plot(plate_x, plate_y, 'k-', linewidth=2)

    # Determine which column holds the pitch type
    pitch_type_col = next(
        (c for c in df.columns if "PitchType" in c or "TaggedPitchType" in c),
        None
    )

    if pitch_type_col is None or "PlateLocSide" not in df.columns or "PlateLocHeight" not in df.columns:
        ax.text(
            0.5, 0.5, f"Missing data for {title}",
            ha='center', va='center', transform=ax.transAxes, fontsize=12
        )
        ax.set_xlim(-2, 2)
        ax.set_ylim(0, 4)
        ax.set_title(title, fontsize=16, fontweight='bold')
        ax.set_xticks([])
        ax.set_yticks([])
        return fig

    # Filter the appropriate points
    if stolen:
        pts = df[df["StolenStrike"] == 1]
    else:
        pts = df[df["StrikeLost"] == 1]

    for ptype in pts[pitch_type_col].dropna().unique():
        subset = pts[pts[pitch_type_col] == ptype].dropna(subset=["PlateLocSide", "PlateLocHeight"])
        if not subset.empty:
            color = pitch_colors.get(ptype, "#9C8975")
            ax.scatter(
                subset["PlateLocSide"], subset["PlateLocHeight"],
                c=color, s=60, alpha=0.8, edgecolors="black", linewidth=0.5, label=ptype
            )

    ax.set_xlim(-2, 2)
    ax.set_ylim(0, 4)
    ax.set_aspect("equal")
    ax.set_title(title, fontsize=16, fontweight="bold")
    ax.set_xticks([])
    ax.set_yticks([])

    if not pts.empty:
        fig.subplots_adjust(right=0.75)
        ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=10)

    return fig


# UI definition with KSU summary and two tabs:
#  - "Strike Zone Analysis": stolen & lost side-by-side
#  - "Throw Analysis": pop time chart, throw speed chart, pop time details table
app_ui = ui.page_fluid(
    ui.layout_sidebar(
        ui.sidebar(
            ui.h4("📊 Upload Trackman CSV"),
            ui.input_file("file1", "Choose CSV File", accept=[".csv"]),
            ui.hr(),
            ui.h4("🔍 Filter Options"),
            ui.input_date_range(
                "date_range",
                "Select Date Range",
                start=None,
                end=None
            ),
            ui.input_select(
                "pitcher_team",
                "Pitcher Team",
                choices=[],
                multiple=True,
            ),
            ui.input_select(
                "catcher",
                "Catcher",
                choices=[],
                multiple=False,
            ),
            width=300,
        ),
        ui.div(
            ui.h3("⚾ Game Summary (KSU)"),
            ui.div(
                ui.output_text("ksu_summary_text"),
                style="font-size: 18px; font-weight: bold; margin: 10px 0;"
            ),
            ui.input_action_button("print_button", "🖨️ Print Report", class_="btn-primary"),
            ui.output_table("ksu_summary_table"),
            ui.br(),
            ui.h3("📈 Analysis Plots"),
            ui.navset_tab(
                ui.nav_panel(
                    "Strike Zone Analysis",
                    ui.layout_columns(
                        ui.column(6, ui.output_plot("stolen_strikes_plot")),
                        ui.column(6, ui.output_plot("lost_strikes_plot")),
                        fill=False
                    ),
                ),
                ui.nav_panel(
                    "Throw Analysis",
                    ui.h4("📊 Pop Time Distribution"),
                    ui.output_plot("pop_time_plot"),
                    ui.br(),
                    ui.h4("🚀 Throw Speed Distribution"),
                    ui.output_plot("throw_speed_plot"),
                    ui.br(),
                    ui.h4("⏱️ Pop Time Details"),
                    ui.output_table("pop_time_table"),
                ),
            ),
        )
    )
)


def server(input, output, session):
    @reactive.Calc
    def raw_data():
        """Read uploaded CSV and compute indicators - cached for performance"""
        fileinfo = input.file1()
        if fileinfo is None:
            return None

        try:
            if isinstance(fileinfo, list) and len(fileinfo) > 0:
                file_path = fileinfo[0]["datapath"]
            elif isinstance(fileinfo, dict):
                file_path = fileinfo["datapath"]
            else:
                return None

            if not os.path.exists(file_path):
                return None

            try:
                df = pd.read_csv(file_path)
            except UnicodeDecodeError:
                df = pd.read_csv(file_path, encoding="latin-1")
            except Exception:
                df = pd.read_csv(file_path, sep=None, engine="python")

            # Convert date column if it exists
            if "Date" in df.columns:
                df["Date"] = pd.to_datetime(df["Date"], errors='coerce')

            df = compute_indicators(df)
            return df

        except Exception:
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

        # Apply team filter
        teams = input.pitcher_team()
        if teams:
            team_col = next(
                (c for c in df.columns if "PitcherTeam" in c or "pitcher_team" in c.lower() or "team" in c.lower()),
                None
            )
            if team_col:
                df = df[df[team_col].isin(teams)]

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
    def update_pitcher_choices():
        df = raw_data()
        if df is None:
            return
        team_col = next(
            (c for c in df.columns if "PitcherTeam" in c or "pitcher_team" in c.lower() or "team" in c.lower()),
            None
        )
        if team_col is None:
            return
        teams = sorted(df[team_col].dropna().astype(str).unique())
        ui.update_select("pitcher_team", choices=teams, session=session)

    @reactive.Effect
    def update_catcher_choices():
        df = filtered_data()
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
        return create_strike_zone_plot(df_ss, "Strikes Stolen", stolen=True)

    @output
    @render.plot
    def lost_strikes_plot():
        df = filtered_data()
        if df is None:
            return create_strike_zone_plot(pd.DataFrame(), "Strikes Lost", stolen=False)
        df_ls = df[df["StrikeLost"] == 1] if "StrikeLost" in df.columns else pd.DataFrame()
        return create_strike_zone_plot(df_ls, "Strikes Lost", stolen=False)

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
        fig, ax = plt.subplots(figsize=(6, 4))
        if df.empty or "PopTime" not in df.columns:
            ax.text(
                0.5, 0.5, "No PopTime data",
                ha="center", va="center", transform=ax.transAxes, fontsize=12
            )
            ax.set_title("Pop Time Distribution", fontsize=14, fontweight="bold")
            ax.set_xticks([])
            ax.set_yticks([])
            return fig

        # Histogram of PopTime
        ax.hist(df["PopTime"].dropna(), bins=10, color="#3025CE", alpha=0.7, edgecolor="black")
        ax.set_title("Pop Time Distribution", fontsize=14, fontweight="bold")
        ax.set_xlabel("Pop Time (sec)")
        ax.set_ylabel("Count")
        plt.tight_layout()
        return fig

    @output
    @render.plot
    def throw_speed_plot():
        df = throwlog_df()
        fig, ax = plt.subplots(figsize=(6, 4))
        if df.empty or "ThrowSpeed" not in df.columns:
            ax.text(
                0.5, 0.5, "No ThrowSpeed data",
                ha="center", va="center", transform=ax.transAxes, fontsize=12
            )
            ax.set_title("Throw Speed Distribution", fontsize=14, fontweight="bold")
            ax.set_xticks([])
            ax.set_yticks([])
            return fig

        # Histogram of ThrowSpeed
        ax.hist(df["ThrowSpeed"].dropna(), bins=10, color="#F79E70", alpha=0.7, edgecolor="black")
        ax.set_title("Throw Speed Distribution", fontsize=14, fontweight="bold")
        ax.set_xlabel("Throw Speed (mph)")
        ax.set_ylabel("Count")
        plt.tight_layout()
        return fig

    @output
    @render.table
    def pop_time_table():
        """
        Instead of ExchangeTime, show a small table of PopTime values
        for every pitch (filtered by selected catcher).
        """
        df = throwlog_df()
        if df.empty or "PopTime" not in df.columns:
            return pd.DataFrame({"Message": ["No PopTime data"]})
        cols = [c for c in ["PitchNo", "Catcher", "PopTime"] if c in df.columns]
        return df[cols].rename(columns={"PopTime": "Pop Time (sec)"})

    @reactive.Effect
    def _():
        input.print_button()
        session.send_custom_message("print", {})

    # End of server()


app = App(app_ui, server)

if __name__ == "__main__":
    app.run()
#bruh