import "./App.css";

import Dashboard from "@/pages/Dashboard";

function App() {
  return (
    <main className="flex min-h-screen flex-col lg:h-screen lg:overflow-hidden">
      <p className="shrink-0 text-xl">Agentic Workbench</p>
      <Dashboard />
    </main>
  );
}

export default App;
