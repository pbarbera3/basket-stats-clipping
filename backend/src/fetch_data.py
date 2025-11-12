import os
import json
import requests
import argparse

SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/summary"


def fetch_json(url: str):
    """GET JSON from URL."""
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json()


def fetch_game_data(game_id: str, save_dir: str = "data/metadata"):
    """
    Fetch ESPN summary data for a given game ID and save as JSON.
    The summary endpoint contains both team info and plays list.
    """
    os.makedirs(save_dir, exist_ok=True)

    url = f"{SUMMARY_URL}?event={game_id}"
    print(f"🌐 Fetching: {url}")
    data = fetch_json(url)

    # Save file
    out_path = os.path.join(save_dir, f"pbp.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    # Extract team names
    comps = data.get("header", {}).get("competitions", [])
    if comps:
        teams = [c["team"]["displayName"]
                 for c in comps[0].get("competitors", [])]
        if len(teams) == 2:
            print(f"✅ Game {game_id}: {teams[0]} vs {teams[1]}")
        else:
            print(f"✅ Game {game_id}: {teams}")
    else:
        print(f"✅ Game {game_id}: (teams not found)")

    print(f"📁 Saved metadata JSON to {out_path}")
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--espn_id", required=True,
                        help="ESPN game ID (e.g. 401813347)")
    parser.add_argument("--save_dir", default="data/metadata",
                        help="Directory to save JSON")
    args = parser.parse_args()

    fetch_game_data(args.espn_id, save_dir=args.save_dir)
