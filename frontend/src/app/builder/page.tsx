"use client";

import { useState } from "react";

export default function BuilderPage() {
  const [text, setText] = useState(
    "3rd & 8 on DAL 42, 2:05 Q4, down 3, deep middle pass, 11 personnel"
  );
  const [offense, setOffense] = useState("DAL");
  const [defense, setDefense] = useState("PHI");
  const [result, setResult] = useState<any>(null);
  const [warning, setWarning] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setWarning(null);
    setResult(null);

    try {
      const base = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
      const res = await fetch(`${base}/parse-freeform`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, offense, defense }),
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

  return (
    <main className="p-6 max-w-3xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Freeform Play Builder</h1>

      <form onSubmit={onSubmit} className="space-y-4">
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
        </>
      )}

      <p className="text-xs text-gray-500">
        API: {process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000"}/parse-freeform
      </p>
    </main>
  );
}
