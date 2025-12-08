import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# --- PREP FUNCTIONS ---

# calculate arm angle function
def arm_angle_calc(data_frame, rosters):
    data_frame = data_frame.copy()

    matched_height = rosters.set_index('NAME').reindex(data_frame['Pitcher'])['height_inches'].values
    fallback_height = rosters.loc[rosters['POSITION'].str.contains("P", na=False), 'height_inches'].mean()

    data_frame['height_inches'] = np.where(
        pd.isna(matched_height), fallback_height, matched_height
    )
    data_frame['arm_length'] = data_frame['height_inches'] * 0.39
    data_frame['RelSide_in'] = data_frame['RelSide'] * 12
    data_frame['RelHeight_in'] = data_frame['RelHeight'] * 12
    data_frame['shoulder_pos'] = data_frame['height_inches'] * 0.70
    data_frame['Adj'] = data_frame['RelHeight_in'] - data_frame['shoulder_pos']
    data_frame['Opp'] = np.abs(data_frame['RelSide_in'])
    data_frame['arm_angle_rad'] = np.arctan2(data_frame['Opp'], data_frame['Adj'])
    data_frame['arm_angle'] = np.degrees(data_frame['arm_angle_rad'])

    data_frame['arm_angle_180'] = np.where(
        data_frame['PitcherThrows'] == 'Left',
        180 - data_frame['arm_angle'],
        np.where(data_frame['PitcherThrows'] == 'Right',
                 180 + data_frame['arm_angle'],
                 data_frame['arm_angle'])
    )

    data_frame['arm_angle_savant'] = np.where(
        data_frame['arm_angle'] <= 90,
        90 - data_frame['arm_angle'],
        90 - data_frame['arm_angle']
    )
    return data_frame.drop(columns=['Opp', 'arm_angle_rad'])

# convert height from feet to inches
def convert_to_inches(height_str):
    for char in ['-', '’', '‘', '"', '/', '?', ':', ';']:
        height_str = height_str.replace(char, "'")
    parts = height_str.split("'")
    feet = float(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 0
    inches = float(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    return feet * 12 + inches

# categorize arm angle
def arm_angle_categories(df):
    bins = [0, 30, 60, 90, 120, 180]
    labels = ['Overhand', 'High Three-Quarters', 'Low Three-Quarters', 'Sidearm', 'Submarine']
    df['arm_angle_type'] = pd.cut(df['arm_angle'], bins=bins, labels=labels, right=False)
    return df

# circle function for savant plot
def circle_fun(center=(0, 0), radius=24, npoints=100):
    tt = np.linspace(0, 2 * np.pi, npoints)
    x = center[0] + radius * np.cos(tt)
    y = center[1] + radius * np.sin(tt)
    return pd.DataFrame({'x': x, 'y': y})

circle = circle_fun(center=(0, 0), radius=24)

# pitcher's mound for ARM ANGLE plot
def create_mound(r=40, height_scale=4, points=100):
    theta = np.linspace(0, np.pi, points)
    x = r * np.cos(theta)
    y = height_scale * np.sin(theta)
    return pd.DataFrame({'x': x, 'y': y})

mound = create_mound()

# pitch colors for SAVANT and MOVEMENT
pitch_colors = pd.DataFrame({
    'TaggedPitchType': ["Fastball", "Sinker", "Cutter", "Curveball",
                        "Slider", "Changeup", "Splitter", "Knuckleball", "Other"],
    'PitchCode': ['FB', 'SI', 'CT', 'CB', 'SL', 'CH', 'SPL', 'KN', 'OT'],
    'Color': ['red', '#a34700', 'gold', 'darkgreen', 'cornflowerblue',
              'violet', 'black', 'black', 'black']
})