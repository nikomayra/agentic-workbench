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
    <>
      {error && <p role="alert">Could not reach backend: {error}</p>}
      {!error && !health && <p>Checking backend health...</p>}
      {health && (
        <ul>
          <li>API status: {health.status}</li>
          <li>Database: {health.database}</li>
        </ul>
      )}
    </>
  );
};

export default ServerStatus;
