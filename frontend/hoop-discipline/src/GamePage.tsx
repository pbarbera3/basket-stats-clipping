import React, { useEffect, useState, useMemo } from "react";
import { useParams, Link } from "react-router-dom";
import Papa from "papaparse";
import "./GamePage.css";

interface Summary {
  logos: { home: string; away: string };
  totals: Record<string, string>;
  player: string;
}

interface Manifest {
  stats: Record<string, { url: string }>;
}

interface Stint {
  id: number;
  half: string;
  start: string;
  end: string;
}

export default function GamePage() {
  const { playerSlug, gameSlug } = useParams();
  const decodedGame = decodeURIComponent(gameSlug || "");
  const base = `https://game-films.s3.us-east-005.backblazeb2.com/${playerSlug}/${encodeURIComponent(decodedGame)}`;


  const [summary, setSummary] = useState<Summary | null>(null);
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [stints, setStints] = useState<Stint[]>([]);
  const [activeStint, setActiveStint] = useState<number>(1);
  const [activeStat, setActiveStat] = useState<string>("");
  const [score, setScore] = useState<{ away: number; home: number }>({
    away: 0,
    home: 0,
  });

  const DISPLAY_STATS = [
    "made_shots",
    "assists",
    "rebounds",
    "steals",
    "blocks",
    "turnovers",
    "fouls",
    "2pt_made",
    "3pt_made",
    "missed_shots"
    ];

  // Format compact stat line: 5 stats (PTS | REB | top2(AST,BLK,STL) | FG)
  function compactStats(t: Record<string, string>): string {
    const pts = t["PTS"];
    const reb = t["REB"];
    const ast = parseFloat(t["AST"] || "0");
    const blk = parseFloat(t["BLK"] || "0");
    const stl = parseFloat(t["STL"] || "0");
    const fg = t["FG"];
    const fgp = t["FG%"];

    // pick 2 best among AST, BLK, STL
    const topTwo = Object.entries({ AST: ast, BLK: blk, STL: stl })
        .sort((a, b) => b[1] - a[1])
        .slice(0, 2)
        .map(([key]) => `${key}: ${t[key]}`); // <-- keep uppercase here

    const parts = [
        `PTS: ${pts}`,
        `REB: ${reb}`,
        ...topTwo,
        `FG: ${fg} (${fgp}%)`,
    ].filter(Boolean);

    return parts.join(" | ");
  }

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
        const videos = document.querySelectorAll("video");
        if (!videos.length) return;

        // find the one that's playing or visible
        videos.forEach((v) => {
        const video = v as HTMLVideoElement;
        if (!video.paused && !video.ended) {
            if (e.key === "ArrowRight") video.currentTime += 10;
            if (e.key === "ArrowLeft") video.currentTime -= 10;
        }
        });
    };

    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, []);



  useEffect(() => {
    (async () => {
      try {
        const s = await (await fetch(`${base}/metadata/summary.json`)).json();
        setSummary(s);

        const m = await (await fetch(`${base}/metadata/manifest.json`)).json();
        setManifest(m);
        const firstStat = Object.keys(m.stats)[0];
        setActiveStat(firstStat);

        const csv = await (await fetch(`${base}/metadata/subs_intervals.csv`)).text();
        const parsed = Papa.parse(csv, { header: true });
        const stintsList: Stint[] = parsed.data
          .filter((r: any) => r.start_clock && r.end_clock)
          .map((r: any, i: number) => ({
            id: i + 1,
            half: r.half || r.period || "",
            start: r.start_clock,
            end: r.end_clock,
          }));
        setStints(stintsList);

        // get score from pbp
        try {
          const pbp = await (await fetch(`${base}/metadata/pbp.json`)).json();
          const lastPlay = pbp?.plays?.slice(-1)[0];
          if (lastPlay?.homeScore && lastPlay?.awayScore) {
            setScore({
              away: Number(lastPlay.awayScore),
              home: Number(lastPlay.homeScore),
            });
          }
        } catch {
          console.warn("no pbp.json score found");
        }
      } catch (err) {
        console.error("❌ Error loading metadata:", err);
      }
    })();
  }, [base]);

  const stintUrl = useMemo(
    () => `${base}/stints/stint_${activeStint}.mp4`,
    [base, activeStint]
  );

  const statUrl = useMemo(
    () => (manifest && activeStat ? manifest.stats[activeStat]?.url : ""),
    [manifest, activeStat]
  );

  if (!summary || !manifest) return <div className="loading">Loading...</div>;

  // Split team names
  const [awayTeam, homeTeam] = decodedGame.split("@").map((s) => s.trim());

  return (
    <div className="game-page">
      <Link to={`/player/${playerSlug}`} className="back-link">
        Back to Games
      </Link>
      {/* Header */}
      <header className="game-header score-layout">
        <div className="team">
          <img src={summary.logos.away} alt={awayTeam} />
          <div className="big-score">{score.away}</div>
        </div>

        <div className="center">
          <h1>{summary.player || playerSlug?.replaceAll("_", " ")}</h1>
          <p>{decodedGame.replaceAll("@", " @ ")}</p>
          <div className="totals">{compactStats(summary.totals)}</div>
        </div>

        <div className="team">
          <div className="big-score">{score.home}</div>
          <img src={summary.logos.home} alt={homeTeam} />
        </div>
      </header>

      {/* Stints Row */}
      <div className="stints-row">
        {stints.map((s) => (
          <button
            key={s.id}
            className={`stint-btn ${s.id === activeStint ? "active" : ""}`}
            onClick={() => setActiveStint(s.id)}
          >
            <>
            {s.half}
            <span className="separator">|</span>
            {s.start} – {s.end}
            </>
          </button>
        ))}
      </div>

      {/* Main stint video */}
      <div className="video-wrap large">
        <video
          key={stintUrl}
          src={stintUrl}
          controls
          playsInline
          preload="auto"
          onWaiting={(e) => console.log("⏳ Buffering stint video")}
          onCanPlay={(e) => console.log("✅ Stint video ready")}
        />
      </div>

      {/* Stat Buttons */}
      <div className="stats-row">
        {DISPLAY_STATS.filter((k) => !!manifest.stats[k]).map((k) => (
            <button
            key={k}
            className={`stat-btn ${k === activeStat ? "active" : ""}`}
            onClick={() => setActiveStat(k)}
            >
            {k.replaceAll("_", " ")}
            </button>
        ))}
      </div>

      {/* Stat video */}
      {activeStat && (
        <div className="video-wrap small">
          <video
            key={statUrl}
            src={statUrl}
            controls
            playsInline
            preload="auto"
            onWaiting={(e) => console.log("⏳ Buffering stat video")}
            onCanPlay={(e) => console.log("✅ Stat video ready")}
          />  
        </div>
      )}
    </div>
  );
}
