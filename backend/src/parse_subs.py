import json
import csv
import os
import re
import argparse

# ===== CONFIG =====
ESPN_JSON = None
OUTPUT_CSV = "data/metadata/subs_intervals.csv"
PLAYER_NAME = None
# ==================


def period_label(num):
    if num == 1:
        return "1st Half"
    elif num == 2:
        return "2nd Half"
    else:
        return f"Overtime {num - 2}"


def clock_to_sec(clock):
    """Convert M:SS string to seconds remaining in half (int)."""
    if not isinstance(clock, str) or ":" not in clock:
        return 0
    m, s = map(int, clock.split(":"))
    return m * 60 + s


def parse_player_subs(json_path, player_name):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    events = data.get("plays", []) or data.get("pbp", [])
    player_events = []

    for ev in events:
        txt = ev.get("text", "")
        clock_raw = ev.get("clock", "")
        if isinstance(clock_raw, dict):
            clock = clock_raw.get("displayValue", "")
        else:
            clock = clock_raw
        period = ev.get("period", {}).get("number", None)

        txt_lower = txt.lower()
        name_lower = player_name.lower()

        # --- Player explicitly subbing in/out ---
        if f"{name_lower} subbing in" in txt_lower:
            player_events.append({
                "half": period_label(period),
                "action": "IN",
                "clock": clock
            })
        elif f"{name_lower} subbing out" in txt_lower:
            player_events.append({
                "half": period_label(period),
                "action": "OUT",
                "clock": clock
            })
        # --- Another player enters for him ---
        elif re.search(r"enters the game for", txt_lower):
            match = re.search(
                r"(.+?) enters the game for (.+)", txt, re.IGNORECASE)
            if match:
                player_in, player_out = match.groups()
                if player_out.strip().lower() == name_lower:
                    player_events.append({
                        "half": period_label(period),
                        "action": "OUT",
                        "clock": clock
                    })
                elif player_in.strip().lower() == name_lower:
                    player_events.append({
                        "half": period_label(period),
                        "action": "IN",
                        "clock": clock
                    })

    # --- Sort by half + descending clock (20:00 → 0:00) ---
    player_events.sort(key=lambda e: (e["half"], -clock_to_sec(e["clock"])))

    # --- Build intervals ---
    intervals = []
    current_half = None
    start_clock = None

    for ev in player_events:
        half = ev["half"]
        action = ev["action"]
        clock = ev["clock"]

        if current_half != half:
            current_half = half
            start_clock = None

        if action == "IN":
            start_clock = clock
        elif action == "OUT" and start_clock:
            intervals.append({
                "half": half,
                "start_clock": start_clock,
                "end_clock": clock
            })
            start_clock = None

    # --- Handle fallback cases ---
    if not intervals:
        # full game (no subs detected)
        intervals = [
            {"half": "1st Half", "start_clock": "20:00", "end_clock": "0:00"},
            {"half": "2nd Half", "start_clock": "20:00", "end_clock": "0:00"},
        ]
        print(
            f"ℹ️ No subs detected for {player_name} — assuming full 40 minutes.")
    else:
        # If an IN exists without matching OUT → assume he finished the half
        for ev in player_events:
            if ev["action"] == "IN" and not any(
                i["half"] == ev["half"] and i["start_clock"] == ev["clock"] for i in intervals
            ):
                intervals.append({
                    "half": ev["half"],
                    "start_clock": ev["clock"],
                    "end_clock": "0:00"
                })

        # Ensure both halves exist
        for half in ["1st Half", "2nd Half"]:
            if not any(i["half"] == half for i in intervals):
                intervals.append({
                    "half": half,
                    "start_clock": "20:00",
                    "end_clock": "0:00"
                })

    # --- Sort again for clean output ---
    intervals.sort(key=lambda i: (i["half"], -clock_to_sec(i["start_clock"])))
    return intervals


def save_subs(intervals, out_path, player_name):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["player", "half", "start_clock", "end_clock"])
        for e in intervals:
            writer.writerow(
                [player_name, e["half"], e["start_clock"], e["end_clock"]])
    print(
        f"✅ Saved {len(intervals)} intervals for {player_name} to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--player", required=True)
    parser.add_argument("--espn_id", required=True)
    args = parser.parse_args()

    PLAYER_NAME = args.player
    ESPN_JSON = f"data/metadata/pbp.json"

    intervals = parse_player_subs(ESPN_JSON, PLAYER_NAME)
    save_subs(intervals, OUTPUT_CSV, PLAYER_NAME)
