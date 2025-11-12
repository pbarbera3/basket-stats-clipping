import cv2
import easyocr
import csv
import os
import re
import argparse

# ======= CONFIG =======
USE_MANUAL_ROI = True
START_SEC = 30
CLOCK_ROI = None
# ======================


def extract_clock_ocr(video_path: str,
                      output_csv: str = "data/metadata/clock_map.csv",
                      sample_rate: int = 1):
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"❌ Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps
    print(f"🎥 Loaded video ({duration/60:.1f} min, {fps:.1f} fps)")

    # Jump ahead 30 sec so clock is visible
    cap.set(cv2.CAP_PROP_POS_MSEC, START_SEC * 1000)

    # ---- Step 1: ROI ----
    ret, frame = cap.read()
    if not ret:
        raise RuntimeError("Could not read frame at 30s mark.")

    if USE_MANUAL_ROI:
        print("🖱 Select ROI window and press ENTER.")
        r = cv2.selectROI("Select Clock Region", frame)
        cv2.destroyWindow("Select Clock Region")
        x, y, w, h = [int(v) for v in r]
    else:
        x, y, w, h = CLOCK_ROI
        print(f"✅ Using predefined ROI: x={x}, y={y}, w={w}, h={h}")

    # ---- Step 2: OCR ----
    reader = easyocr.Reader(["en"], gpu=True)
    frame_interval = int(fps * sample_rate)
    results = []

    cap.set(cv2.CAP_PROP_POS_MSEC, START_SEC * 1000)  # start OCR loop at 30 s

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_id = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
        if frame_id % frame_interval != 0:
            continue

        roi = frame[y:y+h, x:x+w]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=2, fy=2,
                          interpolation=cv2.INTER_CUBIC)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        _, gray = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        text = reader.readtext(gray, detail=0)
        clock_text = None
        for t in text:
            t_clean = t.strip()
            if re.match(r"^\d{1,2}\.\d$", t_clean):
                clock_text = t_clean
                break
            if re.match(r"^\d{1,2}:\d{2}$", t_clean):
                clock_text = t_clean
                break

        if clock_text:
            current_time = frame_id / fps
            results.append((current_time, clock_text))
            if len(results) % 100 == 0:
                print(f"Processed {len(results)} seconds...")

    cap.release()

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["video_time_sec", "clock_text"])
        writer.writerows(results)

    print(f"\n✅ Saved clock OCR map to {output_csv} ({len(results)} entries).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True)
    args = parser.parse_args()
    extract_clock_ocr(args.video)
