import type { QueryClient } from "@tanstack/react-query";
import { apiGet, apiPost } from "@/lib/api";

type ActiveJob = {
  job_id?: string;
  run_id?: string;
  status?: string;
};

/** 실행 중 Job 종료 + pipeline abandon(설정 잠금 해제). 01~04·05~10·전체 일괄 공통. */
export async function cancelPipelineJob(runId: string, qc?: QueryClient): Promise<void> {
  const active = await apiGet<{ job: ActiveJob | null }>("/api/jobs/active");
  const job = active?.job;
  if (
    job &&
    job.run_id === runId &&
    (job.status === "running" || job.status === "starting")
  ) {
    await apiPost("/api/jobs/cancel", {
      job_id: job.job_id,
      run_id: job.run_id,
    });
  }
  await apiPost(`/api/runs/${runId}/pipeline/abandon`, {
    abandon: true,
    opts_edit: true,
  });
  if (qc) {
    void qc.invalidateQueries({ queryKey: ["activeJob"] });
    void qc.invalidateQueries({ queryKey: ["runConfig", runId] });
    void qc.invalidateQueries({ queryKey: ["steps", runId] });
  }
}
