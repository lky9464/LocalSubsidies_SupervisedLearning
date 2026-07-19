"use client";

import { createContext, useContext, useCallback, useEffect, useState } from "react";
import { apiGet, apiPut } from "@/lib/api";
import type { RunRow } from "@/lib/types";

const RUNS_CACHE_KEY = "lsl_runs_cache";
const RUN_ID_CACHE_KEY = "lsl_run_id";

type RunContextValue = {
  runId: string;
  setRunId: (id: string) => Promise<void>;
  runs: RunRow[];
  refreshRuns: () => Promise<void>;
  loading: boolean;
};

const RunContext = createContext<RunContextValue | null>(null);

function loadRunsCache(): RunRow[] {
  try {
    const raw = sessionStorage.getItem(RUNS_CACHE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as RunRow[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function loadRunIdCache(): string {
  try {
    return sessionStorage.getItem(RUN_ID_CACHE_KEY) || "";
  } catch {
    return "";
  }
}

function saveRunsCache(runs: RunRow[], runId: string) {
  try {
    sessionStorage.setItem(RUNS_CACHE_KEY, JSON.stringify(runs));
    if (runId) sessionStorage.setItem(RUN_ID_CACHE_KEY, runId);
  } catch {
    /* ignore quota / private mode */
  }
}

export function RunProvider({ children }: { children: React.ReactNode }) {
  const [runId, setRunIdState] = useState("");
  const [runs, setRuns] = useState<RunRow[]>([]);
  const [loading, setLoading] = useState(true);

  const refreshRuns = useCallback(async () => {
    try {
      const data = await apiGet<{ runs: RunRow[] }>("/api/runs?limit=50", {
        timeoutMs: 10_000,
      });
      setRuns(data.runs);
      saveRunsCache(data.runs, runId);
    } catch {
      const cached = loadRunsCache();
      if (cached.length) setRuns(cached);
    }
  }, [runId]);

  useEffect(() => {
    (async () => {
      try {
        const [cur, list] = await Promise.all([
          apiGet<{ run_id: string }>("/api/session/current-run", { timeoutMs: 10_000 }),
          apiGet<{ runs: RunRow[] }>("/api/runs?limit=50", { timeoutMs: 10_000 }),
        ]);
        const id = cur.run_id || list.runs[0]?.run_id || "";
        setRuns(list.runs);
        setRunIdState(id);
        saveRunsCache(list.runs, id);
      } catch {
        const cachedRuns = loadRunsCache();
        const cachedId = loadRunIdCache();
        if (cachedRuns.length) setRuns(cachedRuns);
        if (cachedId) setRunIdState(cachedId);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const setRunId = useCallback(async (id: string) => {
    const prev = runId;
    setRunIdState(id);
    saveRunsCache(runs, id);
    try {
      await apiPut("/api/session/current-run", { run_id: id });
    } catch {
      setRunIdState(prev);
      saveRunsCache(runs, prev);
    }
  }, [runId, runs]);

  return (
    <RunContext.Provider value={{ runId, setRunId, runs, refreshRuns, loading }}>
      {children}
    </RunContext.Provider>
  );
}

export function useRun() {
  const ctx = useContext(RunContext);
  if (!ctx) throw new Error("useRun outside RunProvider");
  return ctx;
}
