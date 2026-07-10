import { useCallback, useEffect, useState } from "react";
import { getDocuments, getHealth, runIngest } from "./api/client";
import { ChatWindow } from "./components/ChatWindow";
import { Header } from "./components/Header";
import { Sidebar } from "./components/Sidebar";
import type { DocumentInfo, HealthStatus } from "./types";

function App() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [healthError, setHealthError] = useState(false);
  const [rebuilding, setRebuilding] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [healthData, docs] = await Promise.all([getHealth(), getDocuments()]);
      setHealth(healthData);
      setDocuments(docs);
      setHealthError(false);
    } catch {
      setHealthError(true);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleRebuild = async () => {
    setRebuilding(true);
    try {
      await runIngest();
      await refresh();
    } catch {
      setHealthError(true);
    } finally {
      setRebuilding(false);
    }
  };

  return (
    <div className="flex h-screen flex-col">
      <Header health={health} healthError={healthError} onRebuild={handleRebuild} rebuilding={rebuilding} />
      <div className="flex min-h-0 flex-1">
        <Sidebar health={health} documents={documents} onUploaded={refresh} />
        <ChatWindow />
      </div>
    </div>
  );
}

export default App;
