"use client";

import { useState } from "react";

type SimSummary = {
  yards_mean: number;
  yards_p10: number;
  yards_p50: number;
  yards_p90: number;
  td_rate: number;
  fg_rate: number;
  turnover_rate: number;
  assumptions: string[];
  seed: number;
};

type DrivePlay = {
  down: number;
  distance: number;
  yardline_100: number;
  call_type: string;
  yards: number;
  result:
    | "GAIN"
    | "FIRST_DOWN"
    | "TOUCHDOWN"
    | "TURNOVER_ON_DOWNS"
    | "FIELD_GOAL_GOOD"
    | "FIELD_GOAL_MISS"
    | "PUNT";
};

type DriveSummary = {
  plays: DrivePlay[];
  points_for_offense: number;
  time_elapsed_seconds: number;
  ended: "TD" | "FG_GOOD" | "FG_MISS" | "PUNT" | "DOWNS" | "EXHAUSTED";
};

export default function BuilderPage() {
  const [text, setText] = useState(
    "3rd & 8 on DAL 42, 2:05 Q4, down 3, deep middle pass, 11 personnel"
  );
  const [offense, setOffense] = useState("DAL");
  const [defense, setDefense] = useState("PHI");
  const [result, setResult] = useState<any>(null);
  const [warning, setWarning] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [n, setN] = useState(1000);
  const [seed, setSeed] = useState<number | "">(Math.floor(Math.random() * 1e9));

  const [sim, setSim] = useState<SimSummary | null>(null);
  const [drive, setDrive] = useState<DriveSummary | null>(null);

  const API = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

  async function onParse(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setWarning(null);
    setResult(null);
    setSim(null);
    setDrive(null);
    try {
      const res = await fetch(`${API}/parse-freeform`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, offense, defense }),
        cache: "no-store",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setResult(data);
      if (data.warnings?.length) setWarning(data.warnings.join(" | "));
    } catch (err: any) {
      setWarning(err.message || "Request failed");
    } finally {
      setLoading(false);
    }
  }

  async function onSimulatePlay() {
    if (!result?.spec) return;
    setLoading(true);
    setWarning(null);
    setSim(null);
    try {
      const res = await fetch(`${API}/simulate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          spec: result.spec,
          n,
          seed: seed === "" ? undefined : Number(seed),
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: SimSummary = await res.json();
      setSim(data);
    } catch (err: any) {
      setWarning(err.message || "Sim request failed");
    } finally {
      setLoading(false);
    }
  }

  async function onSimulateDrive() {
    if (!result?.spec) return;
    setLoading(true);
    setWarning(null);
    setDrive(null);
    try {
      const res = await fetch(`${API}/simulate-drive`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          spec: result.spec,
          n: 1,
          seed: seed === "" ? undefined : Number(seed),
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: DriveSummary = await res.json();
      setDrive(data);
    } catch (err: any) {
      setWarning(err.message || "Drive sim failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="p-6 max-w-3xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Freeform Play Builder</h1>

      <form onSubmit={onParse} className="space-y-4">
        <div className="space-y-1">
          <label className="text-sm font-medium">Describe a play</label>
          <textarea
            className="w-full border rounded p-2 h-32"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </div>

        <div className="flex gap-3">
          <div className="flex-1 space-y-1">
            <label className="text-sm font-medium">Offense</label>
            <input
              className="w-full border rounded p-2"
              value={offense}
              onChange={(e) => setOffense(e.target.value.toUpperCase())}
              maxLength={4}
            />
          </div>
          <div className="flex-1 space-y-1">
            <label className="text-sm font-medium">Defense</label>
            <input
              className="w-full border rounded p-2"
              value={defense}
              onChange={(e) => setDefense(e.target.value.toUpperCase())}
              maxLength={4}
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="px-4 py-2 rounded bg-black text-white disabled:opacity-50"
        >
          {loading ? "Parsing..." : "Parse & Validate"}
        </button>
      </form>

      {warning && (
        <div className="p-3 bg-yellow-100 border border-yellow-300 rounded text-sm">
          {warning}
        </div>
      )}

      {result && (
        <>
          <h2 className="text-xl font-semibold">Normalized PlaySpec</h2>
          <pre className="bg-gray-100 p-3 rounded overflow-auto text-sm text-black">
            {JSON.stringify(result.spec, null, 2)}
          </pre>

          <div className="mt-4 flex items-center gap-3">
            <label className="text-sm">Samples (n):</label>
            <input
              type="number"
              min={100}
              max={5000}
              step={100}
              value={n}
              onChange={(e) => setN(Number(e.target.value))}
              className="border rounded p-1 w-28"
            />
            <label className="text-sm">Seed:</label>
            <input
              type="number"
              placeholder="random"
              value={seed}
              onChange={(e) => {
                const v = e.target.value;
                setSeed(v === "" ? "" : Number(v));
              }}
              className="border rounded p-1 w-36"
            />

            <button
              type="button"
              onClick={onSimulatePlay}
              disabled={loading}
              className="px-3 py-2 rounded bg-indigo-600 text-white disabled:opacity-50"
              title="Calls /simulate (single-play Monte Carlo)"
            >
              {loading ? "Simulating..." : "Simulate Play"}
            </button>

            <button
              type="button"
              onClick={onSimulateDrive}
              disabled={loading}
              className="px-3 py-2 rounded bg-emerald-600 text-white disabled:opacity-50"
              title="Calls /simulate-drive (drive progression)"
            >
              {loading ? "Simulating..." : "Simulate Drive"}
            </button>
          </div>
        </>
      )}

      {sim && (
        <>
          <h2 className="text-xl font-semibold">Simulation Summary</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <div className="p-3 border rounded">
              <div className="text-xs text-gray-500">Mean Yards</div>
              <div className="text-lg font-semibold">
                {sim.yards_mean.toFixed(2)}
              </div>
            </div>
            <div className="p-3 border rounded">
              <div className="text-xs text-gray-500">P10 / P50 / P90</div>
              <div className="text-lg font-semibold">
                {sim.yards_p10.toFixed(1)} / {sim.yards_p50.toFixed(1)} /{" "}
                {sim.yards_p90.toFixed(1)}
              </div>
            </div>
            <div className="p-3 border rounded">
              <div className="text-xs text-gray-500">TD Rate</div>
              <div className="text-lg font-semibold">
                {(sim.td_rate * 100).toFixed(1)}%
              </div>
            </div>
            <div className="p-3 border rounded">
              <div className="text-xs text-gray-500">FG Rate</div>
              <div className="text-lg font-semibold">
                {(sim.fg_rate * 100).toFixed(1)}%
              </div>
            </div>
            <div className="p-3 border rounded">
              <div className="text-xs text-gray-500">Turnover Rate</div>
              <div className="text-lg font-semibold">
                {(sim.turnover_rate * 100).toFixed(1)}%
              </div>
            </div>
          </div>

          {sim.assumptions?.length > 0 && (
            <div className="text-xs text-gray-500 mt-2">
              Assumptions: {sim.assumptions.join(" • ")} | seed {sim.seed}
            </div>
          )}
        </>
      )}

      {drive && (
        <>
          <h2 className="text-xl font-semibold mt-6">Drive Summary</h2>
          <div className="text-sm text-gray-600">
            Ended: {drive.ended} • Points: {drive.points_for_offense} • Time:{" "}
            {drive.time_elapsed_seconds}s
          </div>
          <div className="mt-2 overflow-auto">
            <table className="w-full text-sm border">
              <thead className="bg-gray-50">
                <tr>
                  <th className="border px-2 py-1 text-left">Down</th>
                  <th className="border px-2 py-1 text-left">Dist</th>
                  <th className="border px-2 py-1 text-left">YL(100)</th>
                  <th className="border px-2 py-1 text-left">Call</th>
                  <th className="border px-2 py-1 text-left">Yards</th>
                  <th className="border px-2 py-1 text-left">Result</th>
                </tr>
              </thead>
              <tbody>
                {drive.plays.map((p, i) => (
                  <tr key={i}>
                    <td className="border px-2 py-1">{p.down}</td>
                    <td className="border px-2 py-1">{p.distance}</td>
                    <td className="border px-2 py-1">{p.yardline_100}</td>
                    <td className="border px-2 py-1">{p.call_type}</td>
                    <td className="border px-2 py-1">{p.yards}</td>
                    <td className="border px-2 py-1">{p.result}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <p className="text-xs text-gray-500">
        API base: {API}. Endpoints used: /parse-freeform, /simulate, /simulate-drive
      </p>
    </main>
  );
}
