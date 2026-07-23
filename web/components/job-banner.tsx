"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import { cancelPipelineJob } from "@/lib/pipeline-cancel";
import type { JobInfo } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";
import { LoadingSpinner } from "@/components/loading-spinner";

export { LoadingSpinner };

export function JobBanner() {
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["activeJob"],
    queryFn: ({ signal }) =>
      apiGet<{ job: JobInfo | null }>("/api/jobs/active", { signal, timeoutMs: 8_000 }),
    refetchIntervalInBackground: false,
    refetchInterval: (q) => {
      const st = q.state.data?.job?.status;
      return st === "running" || st === "starting" ? 3000 : false;
    },
  });

  const job = data?.job;
  if (!job?.status || job.status === "unknown") return null;

  const running = job.status === "running" || job.status === "starting";
  const pct = Math.round((job.progress || 0) * 100);

  async function cancel() {
    if (!job?.run_id) return;
    await cancelPipelineJob(job.run_id, qc);
  }

  if (running) {
    return (
      <Alert className="mb-4 border-indigo-200 bg-indigo-50/80 dark:bg-indigo-950/40">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-1">
            <p className="font-medium">
              실행 중: {job.current_step_label} · 약 {pct}%
            </p>
            <p className="text-xs text-muted-foreground">
              run={job.run_id} · job={job.job_id} · 자동 갱신 3초
            </p>
            {job.message && <p className="text-xs">{job.message}</p>}
            <div className="h-2 w-full max-w-md overflow-hidden rounded-full bg-muted">
              <div
                className="h-full bg-primary transition-all"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
          <Button variant="outline" size="sm" onClick={cancel}>
            Job 취소
          </Button>
        </div>
      </Alert>
    );
  }

  if (job.status === "succeeded") {
    return (
      <Alert variant="success" className="mb-4">
        최근 Job 완료 · {job.run_id}
        {job.message && <span className="ml-2 text-xs">{job.message}</span>}
      </Alert>
    );
  }

  if (job.status === "failed" || job.status === "cancelled") {
    return (
      <Alert variant="destructive" className="mb-4">
        <p className="font-medium">최근 Job {job.status}</p>
        {job.message && (
          <pre className="mt-2 max-h-32 overflow-auto whitespace-pre-wrap text-xs">{job.message}</pre>
        )}
      </Alert>
    );
  }

  return null;
}
