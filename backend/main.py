import os
import json
import subprocess
from pathlib import Path
import sys

# ========== CONFIG ==========
GAME_INFO_PATH = "game_info.json"
PROCESSED_DIR = Path("data/processed")
# =============================


def run_script(script_path: str, args=None):
    """Run a Python script as a subprocess with optional args."""
    cmd = [sys.executable, script_path]
    if args:
        cmd += args
    print(f"\nRunning {script_path} {' '.join(args or [])}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise RuntimeError(
            f"{script_path} failed with exit code {result.returncode}")
    print(f"Finished {script_path}")


def main():
    if not os.path.exists(GAME_INFO_PATH):
        raise FileNotFoundError(
            "Missing game_info.json! Please create it first.")
    with open(GAME_INFO_PATH, "r", encoding="utf-8") as f:
        info = json.load(f)

    player_name = info["player_name"]
    game_name = info["game_name"]
    espn_id = str(info["espn_id"])
    video_path = info["video_path"]

    print("\nGAME INFO")
    print(f"Player: {player_name}")
    print(f"Game:   {game_name}")
    print(f"ESPN ID: {espn_id}")
    print(f"Video:  {video_path}")

    player_folder = PROCESSED_DIR / player_name.replace(" ", "_") / game_name
    intervals_dir = player_folder / "intervals"
    stats_dir = player_folder / "stats"
    metadata_dir = player_folder / "metadata"

    for d in [intervals_dir, stats_dir, metadata_dir]:
        d.mkdir(parents=True, exist_ok=True)

    print(f"\nFolder structure ready at: {player_folder}")

    scripts = [
        ("src/fetch_data.py", ["--espn_id", espn_id]),
        ("src/parse_subs.py", ["--player", player_name, "--espn_id", espn_id]),
        ("src/extract_clock_ocr.py", ["--video", video_path]),
        ("src/clean_clock_csv.py", []),
        ("src/cut_intervals.py", [
            "--player", player_name, "--game", game_name, "--video", video_path]),
        ("src/generate_highlights.py", [
            "--player", player_name, "--game", game_name, "--espn_id", espn_id, "--video", video_path]),
    ]

    raw_ocr_csv = Path("data/metadata/clock_map.csv")
    clean_ocr_csv = Path("data/metadata/clock_map_clean.csv")
    pbp_file = Path("data/metadata/pbp.json")
    subs = Path("data/metadata/subs_intervals.csv")

    for script, args in scripts:
        script_name = os.path.basename(script)

        if script_name == "fetch_data.py" and pbp_file.exists():
            print("Skipping fetch_data.py (play by play cache found)")
            continue
        if script_name == "parse_subs.py" and subs.exists():
            print("Skipping parse_subs.py (subs intervals cache found)")
            continue
        if script_name == "extract_clock_ocr.py" and raw_ocr_csv.exists():
            print("Skipping extract_clock_ocr.py (raw OCR cache found)")
            continue
        if script_name == "clean_clock_csv.py" and clean_ocr_csv.exists():
            print("Skipping clean_clock_csv.py (clean OCR cache found)")
            continue
        if script_name == "cut_intervals.py" and intervals_dir.exists() and any(intervals_dir.glob("*.mp4")):
            print("Skipping cut_intervals.py (intervals already cut)")
            continue
        if script_name == "generate_highlights.py" and stats_dir.exists() and any(stats_dir.glob("*.mp4")):
            print("Skipping generate_highlights.py (stats already generated)")
            continue

        try:
            run_script(script, args)
        except Exception as e:
            print(f"\nPipeline stopped: {e}")
            break

    interval_files = list(intervals_dir.glob("*.mp4"))
    stat_files = list(stats_dir.glob("*.mp4"))

    print("\nSUMMARY")
    print(f"Intervals found: {len(interval_files)}")
    print(f"Stats clips:     {len(stat_files)}")

    if len(interval_files) == 0:
        print("No interval clips found! Check cut_intervals step.")
    else:
        print(f"Pipeline complete! Data ready in {player_folder}")


if __name__ == "__main__":
    main()
