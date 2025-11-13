## Introduction

The _Automated Game Film Breakdown Pipeline_ was originally created to provide a fully automated film-study service for the three players I personally train.  
Instead of relying on coaches, managers, or manual video editing, the system allows them to independently review their games, study their possessions, and track their development — all without waiting for anyone else to prepare their footage.

The pipeline takes only three inputs:  
**(1) the game video** and **(2) the official ESPN play-by-play**, and **(3) the target player's name**.  
From these inputs, the system automatically rebuilds the player’s entire game, aligns actions with the real video timeline, cuts all relevant clips, and publishes a complete breakdown to the web.

The entire process removes all manual work typically required to analyze a basketball game, producing player-specific clips, highlights, and a full film breakdown in minutes.

Although the current implementation is built around NCAA workflows, the system is fully extensible to any league with minor adjustments, and the core concept easily generalizes to team-wide film study.

**Real-world example:** after an Osasuyi’s game, which ended at _9:30 PM_, he left the locker room at _10:30 PM_ with the full game already uploaded, processed, and cut on the website — less than one hour from the final buzzer to a complete film breakdown.

## Live Demo

You can explore the exact film-study interface that the players use:  
**[Open the live website](https://basket-stats-clipping.vercel.app/)**

## Features

### Automated Possession & Play Cutting

- Detects every moment the player is on the court
- Synchronizes ESPN play-by-play timestamps with real video timestamps
- Automatically cuts clips for every possession and every key action, including:
  - **Positive actions**: made shots, assists, rebounds, blocks, steals
  - **Negative actions**: fouls, turnovers, missed shots
- Uses `ffmpeg` for fast, frame-accurate exports

### Automatic Stints Detection

- Parses the ESPN play-by-play to detect all substitution events
- Outputs a clean and standardized CSV file with each stint

Example:

```
player, half, start_clock, end_clock
Andrew Osasuyi, 1st Half, 14:39, 9:24
Andrew Osasuyi, 1st Half, 5:21, 0:00
Andrew Osasuyi, 2nd Half, 15:50, 11:00
Andrew Osasuyi, 2nd Half, 1:28, 0:00
```

- Automatically reconstructs and cuts **video segments for every stint**, producing:

  - `/stints/stint1.mp4`
  - `/stints/stint2.mp4`
  - `/stints/stint3.mp4`
  - ...

- In the React frontend, each stint is displayed as a **separate video section**, so the player can:
  - watch their stints one by one
  - quickly see when they were on the floor during the game

### OCR-Based Game Clock Mapping (with one required manual step)

- The only user input required: **select the game clock region (ROI) once**
- After that, the system automatically:
- runs OCR with EasyOCR + OpenCV
- reads the game clock across thousands of frames
- normalizes formats (e.g., “1900” → “19:00”) and correctly handles decimal-second clocks that appear only in the final minute of each half (e.g., “45.3”, “12.7”, “0.4”)
- generates `clock_map_clean.csv` for accurate second-by-second alignment

### Stats Extraction & Manifest Generation

Extracts:

- box score totals
- game metadata
- team logos
- possession mapping
- Generates:
- `manifest.json` for the React frontend
- `stats.json` for per-game
- Ensures consistent structure across all players and games

### Fully Automated Backend Pipeline

Once the clock ROI is selected, the entire workflow runs automatically:

- OCR clock extraction
- Play-by-play alignment
- Stints detection
- Clip cutting (stints, plays, actions)
- Stats generation
- Manifest creation
- Cloud upload to Backblaze B2
- No further manual steps required

### React Frontend Integration

- Built fully in **React**
- Dynamic player pages
- Game dashboards with:
- stats
- logos
- score
- stints
- action clips
- Automatically reads all metadata and game folders from Backblaze B2
- Designed for fast loading and clean navigation

### Cloud Storage & Delivery (Backblaze B2)

- S3-compatible cloud storage
- Project assets follow a clean and predictable structure:

```
/{player}/{game}/stints
/{player}/{game}/stats
/{player}/{game}/metadata
```

- Ideal for serving large video files and structured metadata to web or mobile clients

### Real-World Speed

- After receiving the full game video, the entire processing pipeline completes in **under 20 minutes**
- Example: Osasuyi’s game ended at **9:30 PM** and the full breakdown was already online at **10:30 PM**, including:
  - all stints
  - all key-action clips
  - stats
  - manifest
  - React frontend ready to browse
- I still had time to manually review a few clips afterwards — everything had been correctly detected and aligned

## Project Architecture

The system is built as a fully automated pipeline that transforms raw inputs  
(full-game video + official ESPN play-by-play identified by game ID) into a complete, player-specific film breakdown published on the web.

### **1. Input Layer**

- Receives the **full-game video** as the main input
- Automatically fetches and parses the **ESPN play-by-play** using the game ID
- Requires a single manual step: selecting the on-screen **game clock region (ROI)** once before OCR begins

### **2. Processing & Synchronization Layer**

- OCR extracts the game clock from thousands of frames
- Clock values are cleaned and normalized (minutes, seconds, and decimal seconds for the final minute)
- Play-by-play actions are aligned with real video timestamps
- Substitution events are used to reconstruct precise on-court intervals (stints)

### **3. Clip & Metadata Generation Layer**

- Cuts all **stints**
- Cuts all **key actions** (made shots, assists, rebounds, steals, but also fouls, turnovers, and missed shots)
- Generates:
  - stats
  - box score totals
  - the stints CSV
  - the final `manifest.json`
- Prepares a clean and consistent folder structure optimized for cloud delivery

### **4. Delivery & Frontend Layer**

- Uploads all generated assets to Backblaze B2 (S3-compatible)
- The React frontend loads everything from the generated manifest
- Stints, actions, and stats are immediately available for the player to browse

This architecture allows the entire workflow to run with almost no manual intervention, producing a complete film-study experience in minutes after receiving the game video.

## Hardware & Performance Considerations

The pipeline is designed so that **almost all processing runs instantly on CPU**, including:

- play-by-play parsing
- stints reconstruction
- metadata generation
- stats extraction
- video cutting with `ffmpeg`

The **only computational bottleneck is OCR**, which benefits greatly from GPU acceleration.

### **Current Hardware**

The system currently runs on a laptop equipped with:

```
NVIDIA GeForce RTX 3060 Laptop GPU
6 GB VRAM
Driver Version: 573.44
CUDA Version: 12.8
```

This is a **mid-tier laptop GPU**: perfectly adequate for development and fast enough for real-time processing, but not comparable to server-grade GPUs for heavy OCR workloads.

### **Why the Pipeline Takes ~20 Minutes**

- OCR must analyze thousands of frames to extract the game clock
- On the RTX 3060 Laptop GPU, OCR runs **6–10× faster** than CPU
- All other components of the pipeline complete in **1–2 minutes**
- Total end-to-end runtime after receiving the full game video: **under 20 minutes**

### **CPU-Only Estimate**

If the entire pipeline were executed without GPU acceleration:

- OCR alone would likely take **60–90 minutes**
- Total processing time would increase to **approximately 1–1.5 hours**

### **Real-World Example**

In practice, the performance is strong enough to deliver near-real-time results.  
For example, Osasuyi’s game ended at **9:30 PM**, and the complete breakdown (stints, key-action clips, stats, and manifest) was already online at **10:30 PM** — with enough time left to manually double-check several clips.

## Technologies Used

The project combines computer vision, OCR, video processing, cloud storage, and a modern web frontend.  
Below is an overview of the main technologies used across the entire pipeline.

### **Backend & Processing**

- **Python 3.11** — core language for the entire pipeline
- **OpenCV** — video frame extraction and preprocessing
- **EasyOCR** — clock recognition and text detection
- **pandas** — structured data manipulation (PBP, stints, stats)
- **ffmpeg** — fast, frame-accurate video cutting
- **tqdm** — progress visualization
- **regex / json / pathlib** — parsing and filesystem management

### **Cloud & Storage**

- **Backblaze B2 (S3 compatible)** — cloud storage for clips, stints, stats, and manifests
- **boto3** — S3 API for uploading structured assets
- Organized per-game folder structure for scalable delivery:

```
/{player}/{game}/stints
/{player}/{game}/stats
/{player}/{game}/metadata
```

### **Frontend**

- **React** — interactive, fast, component-based UI
- **React Router** — dynamic routing based on player/game slugs
- **PapaParse** — CSV parsing in the browser
- **Custom CSS** — handcrafted styling for all components
- **CSS Media Queries** — responsive layout for tablets and mobile devices

### **Infrastructure & Development**

- **CUDA 12.8 + NVIDIA RTX 3060 Laptop GPU** — accelerates OCR stage
- **GitHub** — version control and project documentation
- **Vercel / Local development** — hosting and testing environment

This combination of technologies allows the system to process full-game videos, generate structured film breakdowns, and publish them online in under 20 minutes end-to-end.

## Results

The system has been tested across multiple full NCAA games, evaluating both the accuracy of the cut clips and the correctness of the reconstructed stints and actions.

### **100% alignment accuracy (when play-by-play data is correct)**

After manually reviewing all generated clips and comparing them with the real game footage, the system achieves **100% accuracy** in identifying and cutting each action, as long as the ESPN play-by-play timestamps are correct.

The only potential inaccuracies come from human errors in the live play-by-play feed (e.g., an action logged a few seconds earlier or later).  
These issues:

- occur in **2–3 clips at most per game** (out of ~20–25 total),
- are trivial to fix by adjusting the `pbp.json` generated by `fetch_data.py`,
- do not affect the pipeline’s reliability.

### **Stint behavior (intentional design choice)**

Stints begin when the _previous_ action ends.  
This was originally implemented to visually confirm substitutions during debugging, and has remained because:

- it does not cause any functional problem,
- users can easily skip the first few seconds (left/right arrows),
- it ensures the player entering the floor is visible at the start of the stint clip.

### **Near–real-time performance**

The entire pipeline processes a full game in **under 20 minutes** after receiving the video:

- OCR: heavy step, GPU-accelerated
- Play-by-play sync: instant
- Clip cutting: instant
- Manifest & stats generation: instant
- Upload + frontend ready: a pair of minutes

Example: in Osasuyi’s latest game, which ended at **9:30 PM**, the full breakdown (stints, key-action clips, stats, manifest) was online by **10:30 PM** — with enough time left to manually review several clips.

### **Consistent, predictable output**

Results are deterministic:  
the same input (video + PBP) always produces the same clips, stints, and metadata, ensuring stability and repeatability across games and players.

## License

This project is licensed under a **proprietary “All Rights Reserved” license**.  
No part of this codebase may be copied, reproduced, modified, or used for commercial purposes without explicit written permission from the author.

## Contributions

This is a proprietary project and is not open to external contributions at the moment.  
However, feedback, suggestions, and technical discussions are always welcome.

If you have ideas for improvements or would like to discuss specific aspects of the system, feel free to reach out.

## Author

Developed by **Pietro Barbera**:

- MSCS with a specialization in Artificial Intelligence at Georgia Tech University
- Founder of **Hoop Discipline**

Contact: **pbarbera3@gatech.edu**
