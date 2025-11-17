import csv
import re
import os

# ======= CONFIG =======
INPUT_CSV = "data/metadata/clock_map.csv"
OUTPUT_CSV = "data/metadata/clock_map_clean.csv"

HALF_RESET_MIN = 19 * 60 + 45
OT_RESET_MIN = 4 * 60 + 50
END_THRESHOLD = 2.5
# ======================


def clock_to_seconds(clock: str):
    try:
        if ":" in clock:
            m, s = clock.split(":")
            return int(m) * 60 + int(s)
        return float(clock)
    except Exception:
        return None


def is_period_reset(prev_sec, curr_sec):
    """End (<= END_THRESHOLD) -> start (half or OT window)."""
    return (
        prev_sec is not None and curr_sec is not None and prev_sec <= END_THRESHOLD and (
            HALF_RESET_MIN <= curr_sec <= 20 * 60 or
            OT_RESET_MIN <= curr_sec <= 5 * 60
        )
    )


def smart_clean_sequence(rows):
    """
    rows: list[(video_time_sec, clock_text)]
    Removes OCR spikes but keeps legitimate period resets.
    """
    if not rows:
        return rows

    cleaned = []
    n = len(rows)

    def sec_at(i):
        if 0 <= i < n:
            return clock_to_seconds(rows[i][1])
        return None

    for i in range(n):
        t, clock = rows[i]
        curr = sec_at(i)
        if curr is None:
            continue

        prev = sec_at(i - 1)
        nxt = sec_at(i + 1)

        if prev is None or nxt is None:
            cleaned.append((t, clock))
            continue

        if is_period_reset(prev, curr):
            cleaned.append((t, clock))
            continue

        trio = [x for x in (prev, curr, nxt) if x is not None]
        med = sorted(trio)[len(trio) // 2]

        if abs(curr - med) > 5.0:
            continue

        if (curr - prev) > 2.0 and abs((nxt or curr) - (prev - 1.0)) < 3.0:
            continue

        cleaned.append((t, clock))

    return cleaned


def label_periods(cleaned_rows):
    """
    Add 'half' label walking the time series and bumping when reset detected.
    Returns list of (video_time_sec, clock_text, half_label).
    """
    labeled = []
    period_idx = 1
    prev_sec = None

    def label_for(idx):
        if idx == 1:
            return "1st Half"
        if idx == 2:
            return "2nd Half"
        return f"Overtime {idx - 2}"

    for t, clock in cleaned_rows:
        curr_sec = clock_to_seconds(clock)
        if is_period_reset(prev_sec, curr_sec):
            period_idx += 1
        labeled.append((t, clock, label_for(period_idx)))
        prev_sec = curr_sec

    return labeled


def main():
    if not os.path.exists(INPUT_CSV):
        raise FileNotFoundError(f"Input file not found: {INPUT_CSV}")

    print(f"Loading {INPUT_CSV}...")
    with open(INPUT_CSV, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        _header = next(reader, None)
        rows = []
        for r in reader:
            if len(r) >= 2:
                try:
                    rows.append((float(r[0]), r[1]))
                except:

                    continue

    print(f"Cleaning {len(rows)} entries...")
    cleaned = smart_clean_sequence(rows)
    print(f"Kept {len(cleaned)} entries ({len(rows)-len(cleaned)} removed).")

    labeled = label_periods(cleaned)

    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["video_time_sec", "clock_text", "half"])
        writer.writerows(labeled)

    print(f"Saved labeled CSV → {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
