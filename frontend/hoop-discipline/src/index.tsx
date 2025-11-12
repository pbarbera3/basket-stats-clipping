import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import App from "./App";
import PlayerPage from "./PlayerPage";
import GamePage from "./GamePage";
import { BrowserRouter, Routes, Route } from "react-router-dom";

const root = ReactDOM.createRoot(
  document.getElementById("root") as HTMLElement
);

root.render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        {/* Main players list */}
        <Route path="/" element={<App />} />

        {/* Player’s games */}
        <Route path="/player/:slug" element={<PlayerPage />} />

        {/* Single game stats page */}
        <Route path="/player/:playerSlug/:gameSlug" element={<GamePage />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);
