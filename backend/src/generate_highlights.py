import os
import re
import json
import pandas as pd
import subprocess
from tqdm import tqdm
import argparse
import shutil
from tempfile import mkdtemp

# ===== CONFIG =====
VIDEO_PATH = None
ESPN_JSON = None
PLAYER_NAME = None
GAME_NAME = None
CLOCK_MAP = "data/metadata/clock_map_clean.csv"
FFMPEG_PATH = r"C:\ffmpeg\bin\ffmpeg.exe"
PRE_SEC = 7.5
POST_SEC = 2.5
KEEP_SEGMENTS = False
# ==================

# Plays requiring deep debug
DEBUG_PLAYS = [
    "Connor Turnbull made Jumper. Assisted by Gabriel Pozzato.",
    "Gabriel Pozzato Turnover."
]


def is_deep_debug(text: str) -> bool:
    return text.strip() in DEBUG_PLAYS


def clock_to_seconds(clock_str):
    if not isinstance(clock_str, str):
        clock_str = str(clock_str)
    if ":" in clock_str:
        m, s = map(float, clock_str.split(":"))
        return m * 60 + s
    return float(clock_str)


def find_video_time(clock_df, clock_text, tolerance=5.0):
    """Return closest OCR video_time AND signed delta."""
    val_event = clock_to_seconds(clock_text)
    clock_df = clock_df.copy()
    clock_df["clock_val"] = clock_df["clock_text"].apply(clock_to_seconds)

    # signed and absolute delta
    clock_df["signed_diff"] = clock_df["clock_val"] - val_event
    clock_df["abs_diff"] = clock_df["signed_diff"].abs()

    nearest = clock_df.nsmallest(1, "abs_diff")

    if nearest.empty:
        return None, None

    delta = float(nearest["signed_diff"].iloc[0])
    video_time = float(nearest["video_time_sec"].iloc[0])
    return video_time, delta


def find_video_time_by_period(clock_df, clock_text, period, tolerance=5.0):
    half_map = {1: "1st Half", 2: "2nd Half", 3: "Overtime 1", 4: "Overtime 2"}
    half_label = half_map.get(period, None)
    sub_df = clock_df[clock_df["half"] ==
                      half_label] if "half" in clock_df else clock_df
    return find_video_time(sub_df, clock_text, tolerance)


def categorize_play(play, player_name):
    text = play.get("text", "").lower()
    if not text or player_name.lower() not in text:
        return []

    cats = []
    p = player_name.lower()

    # Skip free throws
    if "free throw" in text:
        return []

    # Assists
    if f"assisted by {p}" in text:
        cats.append("assists")

    # Made/Missed shots
    if f"{p} made" in text or f"{p} missed" in text:
        made = "made" in text
        if "three point" in text:
            cats += ["3pt_made" if made else "3pt_missed", "3pt_all"]
        elif any(k in text for k in ["jumper", "layup", "dunk", "tip"]):
            cats += ["2pt_made" if made else "2pt_missed", "2pt_all"]

        cats += ["made_shots" if made else "missed_shots", "all_shots"]

    # Rebounds
    if "defensive rebound" in text:
        cats += ["def_rebound", "rebounds"]
    elif "offensive rebound" in text:
        cats += ["off_rebound", "rebounds"]

    # Blocks
    if "block" in text:
        cats.append("blocks")

    # Steals
    if f"{p} steal" in text:
        cats.append("steals")

    # Turnovers
    if "turnover" in text or "lost the ball" in text:
        cats.append("turnovers")

    # Fouls
    if f"foul on {p}" in text or f"{p} foul" in text:
        cats.append("fouls")

    return sorted(set(cats))


# ============================= MAIN =============================

def main(output_dir):
    os.makedirs(output_dir, exist_ok=True)

    with open(ESPN_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    plays = data.get("plays", []) or data.get("pbp", [])
    clock_df = pd.read_csv(CLOCK_MAP)

    events = []

    # ---------- PARSE EVENTS ----------
    for play in plays:
        text = play.get("text", "")
        period = (play.get("period", {}) or {}).get("number")
        clock = (play.get("clock", {}) or {}).get(
            "displayValue") or play.get("clock")
        cats = categorize_play(play, PLAYER_NAME)

        if not cats:
            continue

        video_time, delta = find_video_time_by_period(clock_df, clock, period)
        if video_time is None:
            continue

        for c in cats:
            events.append({
                "category": c,
                "period": period,
                "clock": clock,
                "video_time": video_time,
                "delta": delta,
                "text": text
            })

    if not events:
        print("⚠️ No events found.")
        return

    df = pd.DataFrame(events)
    print(f"🎯 Found {len(df)} highlight events for {PLAYER_NAME}")

    temp_root = mkdtemp(prefix="hl_")

    # ---------- CUT CLIPS ----------
    try:
        for category, group in df.groupby("category"):
            group = group.sort_values("video_time").reset_index(drop=True)
            temp_cat_dir = os.path.join(temp_root, category)
            os.makedirs(temp_cat_dir, exist_ok=True)

            print(f"\n🎬 Cutting {len(group)} clips for {category}...")
            segment_paths = []

            for i, row in tqdm(group.iterrows(), total=len(group)):

                real_video_time = row.video_time + row.delta

                start = max(0, real_video_time - PRE_SEC)
                end = real_video_time + POST_SEC

                seg_name = f"{category}_{i:04d}.mp4"
                seg_path = os.path.join(temp_cat_dir, seg_name)
                segment_paths.append(seg_path)

                cmd = [
                    FFMPEG_PATH, "-y",
                    "-ss", f"{start:.2f}", "-to", f"{end:.2f}",
                    "-i", VIDEO_PATH,
                    "-c", "copy",
                    seg_path
                ]

                subprocess.run(cmd, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)

            # merge clips
            concat_txt = os.path.join(temp_cat_dir, "segments.txt")
            with open(concat_txt, "w") as f:
                for p in segment_paths:
                    f.write(f"file '{os.path.abspath(p)}'\n")

            final_out = os.path.join(output_dir, f"{category}.mp4")
            subprocess.run(
                [FFMPEG_PATH, "-f", "concat", "-safe", "0",
                    "-i", concat_txt, "-c", "copy", final_out],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

            print(f"✅ Saved: {final_out}")

            if not KEEP_SEGMENTS:
                shutil.rmtree(temp_cat_dir, ignore_errors=True)

    finally:
        if not KEEP_SEGMENTS:
            shutil.rmtree(temp_root, ignore_errors=True)


# ====================== ENTRY ======================

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--player", required=True)
    parser.add_argument("--game", required=True)
    parser.add_argument("--espn_id", required=True)
    parser.add_argument("--video", required=True)
    args = parser.parse_args()

    PLAYER_NAME = args.player
    GAME_NAME = args.game
    ESPN_JSON = "data/metadata/pbp.json"
    VIDEO_PATH = args.video

    OUTPUT_DIR = os.path.join(
        "data", "processed",
        PLAYER_NAME.replace(" ", "_"),
        GAME_NAME,
        "stats"
    )

    main(OUTPUT_DIR)
