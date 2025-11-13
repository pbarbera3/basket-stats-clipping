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


def was_in_at_end(events, half):
    """Return True if the player is on the floor at the end of the given half."""
    events_half = [e for e in events if e["half"] == half]
    if not events_half:
        return False

    state = False  # False = OUT, True = IN

    for ev in events_half:
        if ev["action"] == "IN":
            state = True
        elif ev["action"] == "OUT":
            state = False

    return state


def parse_player_subs(json_path, player_name):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    events = data.get("plays", []) or data.get("pbp", [])
    player_events = []

    # -----------------------------
    # Extract IN/OUT events
    # -----------------------------
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

        # Generic "enters for" format
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

    # Sort by half + descending clock
    player_events.sort(key=lambda e: (e["half"], -clock_to_sec(e["clock"])))

    # -----------------------------
    # Build base intervals
    # -----------------------------
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

    # -----------------------------
    # Handle intervals that should end at 0:00
    # -----------------------------
    for ev in player_events:
        if ev["action"] == "IN":
            exists = any(
                i["half"] == ev["half"] and i["start_clock"] == ev["clock"]
                for i in intervals
            )
            if not exists:
                intervals.append({
                    "half": ev["half"],
                    "start_clock": ev["clock"],
                    "end_clock": "0:00"
                })

    # -----------------------------
    # 🔥 CROSS-PERIOD FIX
    # -----------------------------
    was_in_first = was_in_at_end(player_events, "1st Half")

    events_2nd = [e for e in player_events if e["half"] == "2nd Half"]

    if was_in_first:
        # Player ended 1st half ON FLOOR → starts 2nd half at 20:00
        first_event = events_2nd[0] if events_2nd else None

        if first_event and first_event["action"] == "OUT":
            intervals.append({
                "half": "2nd Half",
                "start_clock": "20:00",
                "end_clock": first_event["clock"]
            })
        else:
            next_out = next(
                (e for e in events_2nd if e["action"] == "OUT"), None)
            intervals.append({
                "half": "2nd Half",
                "start_clock": "20:00",
                "end_clock": next_out["clock"] if next_out else "0:00"
            })

    # If not in at the end of 1st half → do NOTHING (correct)

    # -----------------------------
    # Sort clean output
    # -----------------------------
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
    ESPN_JSON = "data/metadata/pbp.json"

    intervals = parse_player_subs(ESPN_JSON, PLAYER_NAME)
    save_subs(intervals, OUTPUT_CSV, PLAYER_NAME)
