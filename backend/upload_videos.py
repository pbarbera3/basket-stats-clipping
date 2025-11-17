import os
import json
from pathlib import Path
from urllib.parse import quote
from dotenv import load_dotenv
import boto3

# ====== CONFIG ======
GAME_INFO_PATH = "game_info.json"

with open(GAME_INFO_PATH, "r", encoding="utf-8") as f:
    info = json.load(f)

PLAYER_NAME = info["player_name"]
GAME_NAME = info["game_name"]
# =====================

LOCAL_BASE = Path("data/processed") / PLAYER_NAME.replace(" ", "_") / GAME_NAME
LOCAL_STINTS_DIR = LOCAL_BASE / "intervals"
LOCAL_STATS_DIR = LOCAL_BASE / "stats"
LOCAL_METADATA_DIR = LOCAL_BASE / "metadata"

LOCAL_SUBS_INTERVALS = Path("data/metadata/subs_intervals.csv")
LOCAL_PBP_JSON = Path("data/metadata/pbp.json")

CANDIDATE_STATS = [
    "made_shots", "missed_shots", "all_shots", "assists",
    "blocks", "steals", "turnovers", "rebounds",
    "off_rim", "def_rim", "fouls", "2pt_all", "3pt_all",
    "2pt_made", "2pt_missed", "3pt_made", "3pt_missed"
]

load_dotenv()
B2_BUCKET = os.getenv("B2_BUCKET")
B2_S3_ENDPOINT = os.getenv("B2_S3_ENDPOINT")
B2_REGION = os.getenv("B2_REGION")
B2_KEY_ID = os.getenv("B2_KEY_ID")
B2_APPLICATION_KEY = os.getenv("B2_APPLICATION_KEY")
B2_DOWNLOAD_BASE = os.getenv("B2_DOWNLOAD_BASE").rstrip("/")

s3 = boto3.client(
    "s3",
    endpoint_url=B2_S3_ENDPOINT,
    aws_access_key_id=B2_KEY_ID,
    aws_secret_access_key=B2_APPLICATION_KEY,
    region_name=B2_REGION,
)


def b2_url(key: str) -> str:
    return f"{B2_DOWNLOAD_BASE}/{B2_BUCKET}/{quote(key)}"


def upload(local: Path, key: str) -> str:
    s3.upload_file(str(local), B2_BUCKET, key)
    return b2_url(key)


def enumerate_stints(stints_dir: Path):
    """Return all mp4 stints sorted numerically."""
    files = list(stints_dir.glob("stint_*.mp4"))

    files.sort(key=lambda f: int(f.stem.split("_")[1]))

    return files


def find_stat_videos(stats_dir: Path):
    out = {}
    for cat in CANDIDATE_STATS:
        cand = stats_dir / f"{cat}.mp4"
        if cand.exists():
            out[cat] = cand
    return out


def main():
    player_key = PLAYER_NAME.replace(" ", "_")
    base_prefix = f"{player_key}/{GAME_NAME}"
    manifest = {
        "player": PLAYER_NAME,
        "game": GAME_NAME,
        "stints": [],
        "stats": {},
        "metadata": {}
    }

    if LOCAL_STINTS_DIR.exists():
        stints = enumerate_stints(LOCAL_STINTS_DIR)
        for idx, f in enumerate(stints, start=1):
            key = f"{base_prefix}/stints/{f.name}"
            url = upload(f, key)
            manifest["stints"].append(
                {"n": idx, "file": f.name, "key": key, "url": url})
            print(f"[stint {idx}] {url}")
    else:
        print("No stints folder found, skipping.")

    if LOCAL_STATS_DIR.exists():
        stats = find_stat_videos(LOCAL_STATS_DIR)
        for cat, f in stats.items():
            key = f"{base_prefix}/stats/{cat}.mp4"
            url = upload(f, key)
            manifest["stats"][cat] = {"file": f.name, "key": key, "url": url}
            print(f"[stat {cat}] {url}")
    else:
        print("No stats folder found, skipping.")

    for meta_file, label in [
        (LOCAL_SUBS_INTERVALS, "subs_intervals_csv"),
        (LOCAL_PBP_JSON, "pbp_json")
    ]:
        if meta_file.exists():
            key = f"{base_prefix}/metadata/{meta_file.name}"
            url = upload(meta_file, key)
            manifest["metadata"][label] = {"key": key, "url": url}
            print(f"[meta {label}] {url}")

    manifest_local = LOCAL_METADATA_DIR / "manifest.json"
    manifest_local.parent.mkdir(parents=True, exist_ok=True)
    manifest_local.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    mkey = f"{base_prefix}/metadata/manifest.json"
    upload(manifest_local, mkey)
    print(f"\nUploaded manifest: {b2_url(mkey)}")
    print("Upload complete!")


if __name__ == "__main__":
    LOCAL_BASE.mkdir(parents=True, exist_ok=True)
    main()
