import pandas as pd
import subprocess
import os
from tqdm import tqdm
import argparse

# ======= CONFIG =======
CLOCK_CSV = "data/metadata/clock_map_clean.csv"
SUBS_CSV = "data/metadata/subs_intervals.csv"
VIDEO_PATH = None
PLAYER_NAME = None
GAME_NAME = None
FFMPEG_PATH = r"C:\ffmpeg\bin\ffmpeg.exe"
# ======================


def clock_to_seconds(clock_str):
    """Convert 'M:SS' or 'SS.f' to seconds remaining in the period."""
    if isinstance(clock_str, (int, float)):
        return float(clock_str)
    clock_str = str(clock_str)
    if ":" in clock_str:
        m, s = clock_str.split(":")
        return float(m) * 60.0 + float(s)
    return float(clock_str)


def find_video_time_in_half(clock_df, target_clock, half_label, tol=0.6):
    """Find video time for target clock within the specified half."""
    target_val = clock_to_seconds(target_clock)
    seg = clock_df[clock_df["half"] == half_label]
    if seg.empty:
        return None
    seg = seg.assign(clock_val=seg["clock_text"].apply(clock_to_seconds))
    seg = seg.assign(diff=(seg["clock_val"] - target_val).abs())
    best = seg.nsmallest(1, "diff").iloc[0]
    return float(best["video_time_sec"])


def main(output_dir):
    os.makedirs(output_dir, exist_ok=True)

    clock_df = pd.read_csv(CLOCK_CSV)
    subs_df = pd.read_csv(SUBS_CSV)
    intervals = subs_df[subs_df["player"] == PLAYER_NAME].copy()

    print(f"Cutting {len(intervals)} intervals for {PLAYER_NAME}...\n")

    for i, row in tqdm(intervals.iterrows(), total=len(intervals),
                       desc="Processing intervals", ncols=80):
        half_label = row["half"]
        start_clock = row["start_clock"]
        end_clock = row["end_clock"]

        start_time = find_video_time_in_half(clock_df, start_clock, half_label)
        end_time = find_video_time_in_half(clock_df, end_clock, half_label)

        if start_time is None or end_time is None:
            print(
                f"\nSkipping {half_label}: {start_clock} → {end_clock} (no match)")
            continue

        if start_time > end_time:
            start_time, end_time = end_time, start_time

        clip_name = f"stint_{i + 1}.mp4"
        clip_path = os.path.join(output_dir, clip_name)

        cmd = [
            FFMPEG_PATH, "-y",
            "-ss", f"{start_time:.3f}",
            "-to", f"{end_time:.3f}",
            "-i", VIDEO_PATH,
            "-c", "copy",
            clip_path
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)

    print(f"\nDone! {len(intervals)} intervals saved in {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--player", required=True)
    parser.add_argument("--game", required=True)
    parser.add_argument("--video", required=True)
    args = parser.parse_args()

    PLAYER_NAME = args.player
    GAME_NAME = args.game
    VIDEO_PATH = args.video

    OUTPUT_DIR = os.path.join(
        "data", "processed",
        PLAYER_NAME.replace(" ", "_"),
        GAME_NAME,
        "intervals"
    )

    main(OUTPUT_DIR)
