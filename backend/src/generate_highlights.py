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
KEEP_SEGMENTS = False  # set True if you want to keep the per-play clips
# ==================


def clock_to_seconds(clock_str):
    if not isinstance(clock_str, str):
        clock_str = str(clock_str)
    if ":" in clock_str:
        m, s = map(float, clock_str.split(":"))
        return m * 60 + s
    return float(clock_str)


def find_video_time(clock_df, clock_text):
    val = clock_to_seconds(clock_text)
    clock_df = clock_df.copy()
    clock_df["clock_val"] = clock_df["clock_text"].apply(clock_to_seconds)
    near = clock_df.loc[(clock_df["clock_val"] >= val - 0.5) &
                        (clock_df["clock_val"] <= val + 0.5)]
    if near.empty:
        return None
    row = near.nsmallest(1, "video_time_sec")
    return float(row["video_time_sec"].iloc[0])


def find_video_time_by_period(clock_df, clock_text, period):
    half_map = {1: "1st Half", 2: "2nd Half", 3: "Overtime 1", 4: "Overtime 2"}
    half_label = half_map.get(period, None)
    sub_df = clock_df[clock_df["half"] == half_label] if (
        "half" in clock_df.columns and half_label) else clock_df
    return find_video_time(sub_df, clock_text)


def categorize_play(play, player_name):
    text = play.get("text", "").lower()
    participants = [
        p.get("athlete", {}).get("displayName", "").lower()
        for p in play.get("participants", [])
    ]
    if player_name.lower() not in text and all(player_name.lower() not in p for p in participants):
        return []
    cats = []

    # --- skip shots if the player is the assister ---
    if re.search(rf"assist by {re.escape(player_name.lower())}", text):
        # we'll handle this case below in assists
        pass
    else:
        # --- Shots (only if not "assist by player") ---
        if "made" in text or "missed" in text:
            if "three point" in text:
                cats += (["3pt_made", "made_shots", "all_shots", "3pt_all"]
                         if "made" in text else
                         ["3pt_missed", "missed_shots", "all_shots", "3pt_all"])
            elif any(k in text for k in ["jumper", "layup", "dunk", "tip"]):
                cats += (["2pt_made", "made_shots", "all_shots", "2pt_all"]
                         if "made" in text else
                         ["2pt_missed", "missed_shots", "all_shots", "2pt_all"])

    # --- Assists ---
    if "assist" in text:
        if re.search(rf"assist by {re.escape(player_name.lower())}", text):
            cats.append("assists")  # player made the assist
        elif re.search(rf"{re.escape(player_name.lower())} makes", text) or \
                re.search(rf"{re.escape(player_name.lower())} misses", text):
            # player is shooter, not assister — handled above
            pass

    # --- Other stats ---
    if "steal" in text:
        cats.append("steals")
    if "block" in text:
        cats.append("blocks")
    # --- Rebounds ---
    if re.search(rf"{re.escape(player_name.lower())}.*offensive rebound", text):
        cats += ["off_rim", "rebounds"]
    elif re.search(rf"{re.escape(player_name.lower())}.*defensive rebound", text):
        cats += ["def_rim", "rebounds"]
    elif "offensive rebound" in text or "defensive rebound" in text:
        # generic backup (covers other edge cases)
        cats += ["rebounds"]
    # --- Turnovers ---
    if re.search(rf"{re.escape(player_name.lower())}.*turnover", text) or \
            re.search(rf"{re.escape(player_name.lower())}.*lost the ball", text):
        cats.append("turnovers")
    elif "turnover" in text or "lost the ball" in text:
        cats.append("turnovers")
    if "foul" in text:
        cats.append("fouls")

    return cats


def main(output_dir):
    os.makedirs(output_dir, exist_ok=True)

    with open(ESPN_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    plays = data.get("plays", []) or data.get("pbp", [])  # fallback

    clock_df = pd.read_csv(CLOCK_MAP)

    events = []
    for play in plays:
        cats = categorize_play(play, PLAYER_NAME)
        if not cats:
            continue
        clock = (play.get("clock", {}) or {}).get(
            "displayValue") or play.get("clock")
        period = (play.get("period", {}) or {}).get("number")
        if not clock or not period:
            continue
        t = find_video_time_by_period(clock_df, clock, period)
        if t is None:
            continue
        for c in cats:
            events.append({"category": c, "period": period,
                          "clock": clock, "video_time": t})

    if not events:
        print("⚠️ No matching plays found for player.")
        return

    df = pd.DataFrame(events)
    print(f"🎯 Found {len(df)} highlight events for {PLAYER_NAME}")

    # Create a temp workspace for per-play clips (deleted after concat)
    temp_root = mkdtemp(prefix="hl_")

    try:
        for category, group in df.groupby("category"):
            # chronological
            group = group.sort_values("video_time").reset_index(drop=True)
            temp_cat_dir = os.path.join(temp_root, category)
            os.makedirs(temp_cat_dir, exist_ok=True)

            print(f"\n🎬 Cutting {len(group)} clips for {category}...")
            segment_paths = []

            for i, row in tqdm(group.iterrows(), total=len(group), desc=category, ncols=80):
                start = max(0, row.video_time - PRE_SEC)
                end = row.video_time + POST_SEC
                seg_name = f"{category}_{i:04d}.mp4"
                seg_path = os.path.join(temp_cat_dir, seg_name)
                segment_paths.append(seg_path)

                cmd = [
                    FFMPEG_PATH, "-y",
                    "-ss", f"{start:.2f}", "-to", f"{end:.2f}",
                    "-i", VIDEO_PATH, "-c", "copy", seg_path
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)

            # concat list
            concat_txt = os.path.join(temp_cat_dir, "segments.txt")
            with open(concat_txt, "w", encoding="utf-8") as f:
                for p in segment_paths:
                    f.write(f"file '{os.path.abspath(p)}'\n")

            final_out = os.path.join(output_dir, f"{category}.mp4")
            os.makedirs(os.path.dirname(final_out), exist_ok=True)
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
    print("\n🏁 All categories processed!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--player", required=True)
    parser.add_argument("--game", required=True)
    parser.add_argument("--espn_id", required=True)
    parser.add_argument("--video", required=True)
    args = parser.parse_args()

    PLAYER_NAME = args.player
    GAME_NAME = args.game
    ESPN_JSON = f"data/metadata/pbp.json"
    VIDEO_PATH = args.video

    # Dynamic output path: data/processed/<player>/<game>/stats/
    OUTPUT_DIR = os.path.join(
        "data", "processed",
        PLAYER_NAME.replace(" ", "_"),
        GAME_NAME,
        "stats"
    )
    main(OUTPUT_DIR)
