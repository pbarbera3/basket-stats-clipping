import React, { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import "./PlayerPage.css";

interface Game {
  name: string;
  slug: string;
}

interface Player {
  name: string;
  slug: string;
  team: string;
  teamColor?: string;
  games: Game[];
}


interface Totals {
  [key: string]: string;
}

interface CardData {
  game: Game;
  logos?: { home: string; away: string };
  totals?: Totals;
  score?: { away: number; home: number };
}

export default function PlayerPage() {
  const { slug } = useParams<{ slug: string }>();
  const [player, setPlayer] = useState<Player | null>(null);
  const [cards, setCards] = useState<CardData[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    async function run() {
      const response = await fetch("/players.json");
      const data: Player[] = await response.json();
      const found = data.find((p) => p.slug === slug) || null;
      setPlayer(found);
      if (!found) return;

      const rows = await Promise.all(
        found.games.map(async (g) => {
          const base = `https://f005.backblazeb2.com/file/game-films/${found.slug}/${encodeURIComponent(
            g.slug
          )}`;

          let logos, totals, score;
          try {
            const s = await (await fetch(`${base}/metadata/summary.json`)).json();
            logos = s.logos;
            totals = s.totals;
          } catch {}

          try {
            const pbp = await (await fetch(`${base}/metadata/pbp.json`)).json();
            const last = pbp?.plays?.slice(-1)[0];
            if (last?.homeScore != null && last?.awayScore != null)
              score = { away: Number(last.awayScore), home: Number(last.homeScore) };
          } catch {}

          return { game: g, logos, totals, score } as CardData;
        })
      );
      setCards(rows);
    }
    run();
  }, [slug]);

  if (!player) return <div className="loading">Loading player...</div>;

  function getTopStats(t: Totals) {
    const metrics = [
      { key: "AST", val: parseFloat(t["AST"] || "0") },
      { key: "BLK", val: parseFloat(t["BLK"] || "0") },
      { key: "STL", val: parseFloat(t["STL"] || "0") },
    ];
    return metrics.sort((a, b) => b.val - a.val).slice(0, 2).map((m) => m.key);
  }

  function GameCard({
    data,
    playerSlug,
  }: {
    data: CardData;
    playerSlug: string;
  }) {
    const [teamA, teamB] = data.game.name.split("@").map((s) => s.trim());

    const clean = (s: string) =>
      s
        .trim()
        .toLowerCase()
        .replace(/\./g, "")
        .replace(/\s+/g, "")
        .replace(/[^a-z0-9_-]/g, "");

    const logoA =
      data.logos?.away ??
      `https://f005.backblazeb2.com/file/game-films/${playerSlug}/${data.game.slug}/logos/${clean(
        teamA
      )}.png`;

    const logoB =
      data.logos?.home ??
      `https://f005.backblazeb2.com/file/game-films/${playerSlug}/${data.game.slug}/logos/${clean(
        teamB
      )}.png`;

    const t = data.totals || {};
    const topTwo = getTopStats(t);
    const fg = t["FG"] ?? "—";
    const fgp = t["FG%"] ?? "—";

    const statLine = [
      `PTS: ${t["PTS"] ?? "—"}`,
      `REB: ${t["REB"] ?? "—"}`,
      `${topTwo[0]}: ${t[topTwo[0]] ?? "—"}`,
      `${topTwo[1]}: ${t[topTwo[1]] ?? "—"}`,
      `FG: ${fg} (${fgp}%)`,
    ].join(" | ");

    return (
      <div
        className="game-card"
        onClick={() => navigate(`/player/${playerSlug}/${data.game.slug}`)}
      >
        <div className="logos-row">
          <div className="team-block">
            <img src={logoA} alt={teamA} className="team-logo" />
            {data.score && <div className="score-num">{data.score.away}</div>}
          </div>

          <span className="vs-text">@</span>

          <div className="team-block">
            {data.score && <div className="score-num">{data.score.home}</div>}
            <img src={logoB} alt={teamB} className="team-logo" />
          </div>
        </div>

        <div className="game-info">
          <h2 className="game-name">{data.game.name}</h2>
          <p className="game-subtext">View game</p>
          <div className="compact-stats">{statLine}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="playerpage-container">
      <Link to="/" className="back-link">
        Back to Players
      </Link>

      <h1 className="playerpage-title">{player.name}</h1>

      <div className="games-grid">
        {cards.map((c) => (
          <GameCard key={c.game.slug} data={c} playerSlug={player.slug} />
        ))}
      </div>
    </div>
  );
}
