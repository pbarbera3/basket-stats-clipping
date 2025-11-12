import os
import json
import requests
from pathlib import Path
from dotenv import load_dotenv
import boto3
from urllib.parse import quote

# ===== CONFIG =====
GAME_INFO_PATH = "game_info.json"

with open(GAME_INFO_PATH, "r", encoding="utf-8") as f:
    info = json.load(f)

PLAYER_NAME = info["player_name"]
GAME_NAME = info["game_name"]
PLAYER_ID = str(info.get("player_id", "")) or None  # optional field

PLAYER_PHOTO_URL = (
    f"https://a.espncdn.com/i/headshots/mens-college-basketball/players/full/{PLAYER_ID}.png"
    if PLAYER_ID else None
)

# Allow both jpg and png locally
LOCAL_PHOTO_JPG = Path(f"data/photos/{PLAYER_NAME.replace(' ', '_')}.jpg")
LOCAL_PHOTO_PNG = Path(f"data/photos/{PLAYER_NAME.replace(' ', '_')}.png")

LOCAL_PBP_JSON = Path("data/metadata/pbp.json")
# ==================

# ---- Backblaze ----
load_dotenv()
B2_BUCKET = os.getenv("B2_BUCKET")
B2_S3_ENDPOINT = os.getenv("B2_S3_ENDPOINT")
B2_REGION = os.getenv("B2_REGION")
B2_KEY_ID = os.getenv("B2_KEY_ID")
B2_APPLICATION_KEY = os.getenv("B2_APPLICATION_KEY")
B2_DOWNLOAD_BASE = os.getenv("B2_DOWNLOAD_BASE", "").rstrip("/")

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


def object_exists(bucket: str, key: str) -> bool:
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except s3.exceptions.ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey", "NotFound"):
            return False
        raise


def find_existing_remote_photo(player_key: str) -> tuple[str, str] | tuple[None, None]:
    """
    Check B2 for an existing photo; returns (key, url) or (None, None).
    Prefer jpg, then png (or flip this if you prefer png first).
    """
    for ext in ("jpg", "png"):
        key = f"{player_key}/photo.{ext}"
        if object_exists(B2_BUCKET, key):
            return key, b2_url(key)
    return None, None


def pick_local_photo() -> tuple[Path | None, str | None]:
    """
    Return (path, ext) for a local photo if present, preferring JPG then PNG.
    """
    if LOCAL_PHOTO_JPG.exists():
        return LOCAL_PHOTO_JPG, "jpg"
    if LOCAL_PHOTO_PNG.exists():
        return LOCAL_PHOTO_PNG, "png"
    return None, None


def download_photo_from_espn(dst: Path) -> bool:
    try:
        r = requests.get(PLAYER_PHOTO_URL, timeout=10)
        if r.ok:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(r.content)
            print(f"✅ Downloaded player photo from ESPN: {PLAYER_PHOTO_URL}")
            return True
        print(f"⚠️ Failed to fetch player photo (status {r.status_code})")
        return False
    except Exception as e:
        print(f"⚠️ Error downloading photo: {e}")
        return False


def parse_game_name(game_name: str):
    """Split 'TeamA@TeamB' into ('TeamA', 'TeamB')."""
    if "@" in game_name:
        away, home = game_name.split("@", 1)
        return away.strip(), home.strip()
    return game_name, ""


def main():
    player_key = PLAYER_NAME.replace(" ", "_")
    base_prefix = f"{player_key}/{GAME_NAME}"

    summary = {
        "player": PLAYER_NAME,
        "photo": "",
        "game": GAME_NAME,
        "logos": {},
        "totals": {},
        "metadata": {}
    }

    # --- PLAYER PHOTO (upload only if NOT already in B2) ---
    remote_key, remote_url = find_existing_remote_photo(player_key)
    if remote_url:
        summary["photo"] = remote_url
        print(f"✅ Player photo already in B2: {remote_url}")
    else:
        # Try local first
        local_photo, ext = pick_local_photo()

        # If no local photo, try ESPN (if we have PLAYER_ID)
        if not local_photo and PLAYER_ID and PLAYER_PHOTO_URL:
            local_photo = LOCAL_PHOTO_PNG  # save ESPN headshot as PNG
            ext = "png"
            ok = download_photo_from_espn(local_photo)
            if not ok:
                local_photo, ext = None, None

        if local_photo:
            key = f"{player_key}/photo.{ext}"
            url = upload(local_photo, key)
            summary["photo"] = url
            print(f"✅ Uploaded player photo: {url}")
        else:
            print("ℹ️ Skipping player photo upload (no local photo and/or no PLAYER_ID).")

    # --- Load ESPN JSON ---
    if not LOCAL_PBP_JSON.exists():
        print("❌ Missing pbp.json, cannot extract game info.")
        return
    pbp = json.load(open(LOCAL_PBP_JSON, encoding="utf-8"))

    # --- Parse teams and logos ---
    away_name, home_name = parse_game_name(GAME_NAME)
    comp = pbp.get("header", {}).get("competitions", [{}])[0]
    competitors = comp.get("competitors", [])
    summary["metadata"]["game_info"] = {
        "venue": comp.get("venue", {}).get("fullName"),
        "date": comp.get("date"),
        "teams": []
    }

    for team_data in competitors:
        team = team_data.get("team", {}) or {}
        side = team_data.get("homeAway", "team")
        display = team.get("displayName")
        logo_url = team.get("logo")

        if not logo_url:
            logos = team.get("logos") or []
            if logos and isinstance(logos, list) and "href" in (logos[0] or {}):
                logo_url = logos[0]["href"]

        # Canonical logo filename by side to avoid duplicates
        logo_filename = f"{side}.png"

        # Download + upload (always safe to overwrite logos)
        if logo_url:
            try:
                lr = requests.get(logo_url, timeout=10)
                if lr.ok:
                    local_logo = Path(f".tmp_logo_{side}.png")
                    local_logo.write_bytes(lr.content)
                    key = f"{base_prefix}/logos/{logo_filename}"
                    logo_b2 = upload(local_logo, key)
                    local_logo.unlink(missing_ok=True)
                    summary["logos"][side] = logo_b2
                    print(f"✅ Uploaded {side} logo ({display}): {logo_b2}")
                else:
                    print(f"⚠️ Failed to download logo for {display}")
            except Exception as e:
                print(f"⚠️ Error fetching {display} logo: {e}")

        summary["metadata"]["game_info"]["teams"].append({
            "side": side,
            "name": display,
            "abbreviation": team.get("abbreviation"),
            "score": team_data.get("score"),
            "record": (team_data.get("record") or [{}])[0].get("summary"),
            "color": team.get("color"),
            "logo": summary["logos"].get(side)
        })

    print("✅ Extracted teams and named logos from ESPN JSON")

    # --- Extract and embed boxscore ---
    boxscore = pbp.get("boxscore", {}).get("players", [])
    summary["metadata"]["boxscore"] = boxscore

    player_totals = {}
    if PLAYER_ID:
        for team in boxscore:
            for stat_group in team.get("statistics", []) or []:
                names = stat_group.get("names", []) or []
                for athlete in stat_group.get("athletes", []) or []:
                    a = athlete.get("athlete", {}) or {}
                    if a.get("id") == PLAYER_ID:
                        stats_values = athlete.get("stats", []) or []
                        player_totals = dict(zip(names, stats_values))
                        summary["totals"] = player_totals
                        print("✅ Extracted player totals from ESPN boxscore")
                        break
                if player_totals:
                    break
            if player_totals:
                break
    else:
        print("ℹ️ PLAYER_ID not provided; skipping totals extraction.")

    if not player_totals and PLAYER_ID:
        print("⚠️ Could not find player totals (check ID or JSON structure).")

    # --- Upload summary manifest ---
    manifest_local = Path(
        f"data/processed/{player_key}/{GAME_NAME}/metadata/summary.json"
    )
    manifest_local.parent.mkdir(parents=True, exist_ok=True)
    manifest_local.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    key = f"{base_prefix}/metadata/summary.json"
    upload(manifest_local, key)
    print(f"\n🏁 Summary uploaded: {b2_url(key)}")


if __name__ == "__main__":
    main()
