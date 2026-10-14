import "./App.css";

import Dashboard from "@/pages/Dashboard";

function App() {
  return (
    <main className="flex min-h-screen flex-col text-copy lg:h-screen lg:overflow-hidden">
      <header className="shrink-0 border-b border-line bg-canvas/80 px-5 py-4 backdrop-blur">
        <div className="mx-auto flex w-full max-w-[1800px] items-end justify-between gap-4">
          <div>
            <p className="text-xs font-semibold tracking-[0.22em] text-copy-muted uppercase">
              Engineering control plane
            </p>
            <h1 className="mt-1 text-xl font-semibold tracking-tight">
              Agentic Workbench
            </h1>
          </div>
          <p className="hidden text-sm text-copy-muted sm:block">
            Issue → plan → guarded implementation → draft PR
          </p>
        </div>
      </header>
      <div className="mx-auto flex min-h-0 w-full max-w-[1800px] flex-1 p-4 lg:p-5">
        <Dashboard />
      </div>
    </main>
  );
}

export default App;
