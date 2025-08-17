export default async function HealthPage() {
  const base = process.env.NEXT_PUBLIC_API_BASE!;
  const res = await fetch(`${base}/health`, { cache: "no-store" });
  const data = await res.json();

  return (
    <main className="p-8">
      <h1 className="text-2xl font-bold">Backend Health</h1>
      <pre className="mt-4 bg-gray-100 p-4 rounded">{JSON.stringify(data, null, 2)}</pre>
      <p className="mt-2 text-sm text-gray-600">From: {base}/health</p>
    </main>
  );
}
