import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import "./App.css";

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

function generateAccent(hex: string = "#888") {
  try {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);

    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    let h = 0,
      s = 0,
      l = (max + min) / 510;

    const d = max - min;
    if (d !== 0) {
      s = d / (255 - Math.abs(2 * l * 255 - 255));
      switch (max) {
        case r:
          h = (g - b) / d + (g < b ? 6 : 0);
          break;
        case g:
          h = (b - r) / d + 2;
          break;
        case b:
          h = (r - g) / d + 4;
          break;
      }
      h /= 6;
    }

    const newH = h;
    const newS = Math.min(s * 1.35, 1);
    const newL = Math.min(l * 1.5 + 0.08, 0.85);

    const toRGB = (p: number, q: number, t: number) => {
      if (t < 0) t += 1;
      if (t > 1) t -= 1;
      if (t < 1 / 6) return p + (q - p) * 6 * t;
      if (t < 1 / 2) return q;
      if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
      return p;
    };

    const q = newL < 0.5 ? newL * (1 + newS) : newL + newS - newL * newS;
    const p = 2 * newL - q;

    const R = Math.round(toRGB(p, q, newH + 1 / 3) * 255);
    const G = Math.round(toRGB(p, q, newH) * 255);
    const B = Math.round(toRGB(p, q, newH - 1 / 3) * 255);

    return `rgb(${R}, ${G}, ${B})`;
  } catch {
    return "#aaa";
  }
}

function App() {
  const [players, setPlayers] = useState<Player[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    async function fetchPlayers() {
      try {
        const response = await fetch("/players.json");
        const data = await response.json();
        setPlayers(data);
      } catch (error) {
        console.error("Failed to fetch players:", error);
      } finally {
        setLoading(false);
      }
    }
    fetchPlayers();
  }, []);

  if (loading) {
    return <div className="loading">Loading players...</div>;
  }

  return (
    <div className="app-container">
      <h1>Hoop Discipline Players</h1>

      <div className="players-grid">
        {players.map((p) => {
          const accent = generateAccent(p.teamColor);

          return (
            <div
              key={p.slug}
              className="player-card"
              onClick={() => navigate(`/player/${p.slug}`)}
            >
              <img
                src={`https://f005.backblazeb2.com/file/game-films/${p.slug}/photo/${p.slug}.jpg`}
                alt={p.name}
              />

              <div className="player-info">
                <h2>{p.name}</h2>

                <p className="team-name" style={{ color: accent }}>
                  {p.team}
                </p>

                <p className="view-link">View player games</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default App;
