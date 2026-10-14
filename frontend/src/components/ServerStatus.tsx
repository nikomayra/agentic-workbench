import { useEffect, useState } from "react";

type HealthResponse = {
  status: string;
  database: string;
};

const BASE_URL = import.meta.env.VITE_API_BASE_URL;

const ServerStatus = () => {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${BASE_URL}/health`)
      .then((res) => {
        if (!res.ok) throw new Error(`Backend responded with ${res.status}`);
        return res.json() as Promise<HealthResponse>;
      })
      .then(setHealth)
      .catch((err: Error) => setError(err.message));
  }, []);

  return (
    <div className="flex items-center gap-2 text-sm text-copy-muted">
      <span
        className={`size-2 rounded-full ${error ? "bg-rose-400" : health ? "bg-emerald-400" : "animate-pulse bg-amber-400"}`}
      />
      {error && <p role="alert">Backend unavailable: {error}</p>}
      {!error && !health && <p>Checking services…</p>}
      {health && (
        <p>
          API {health.status} · Database {health.database}
        </p>
      )}
    </div>
  );
};

export default ServerStatus;
