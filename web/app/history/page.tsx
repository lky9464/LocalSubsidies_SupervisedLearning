"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import { useRun } from "@/components/run-context";
import { Alert } from "@/components/ui/alert";
import { DataTable, DualMatrices } from "@/components/matrix-table";
import type { RunRow } from "@/lib/types";

export default function HistoryPage() {
  const { runId } = useRun();
  const [pick, setPick] = useState(runId);

  const { data: runsData } = useQuery({
    queryKey: ["runs", 50],
    queryFn: () => apiGet<{ runs: RunRow[] }>("/api/runs?limit=50"),
  });

  const active = pick || runId;

  const { data } = useQuery({
    queryKey: ["history", active],
    queryFn: () => apiGet<Record<string, unknown>>(`/api/runs/${active}/history`),
    enabled: !!active,
  });

  const runRows =
    runsData?.runs.map((r) => ({
      run_id: r.run_id,
      발급시각: r.created_at?.slice(0, 19).replace("T", " ") || "",
      작업자: r.operator,
      작업내용: r.work_content,
      비고: r.note,
      상태: r.status,
    })) || [];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">Run 이력</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          조회 전용 · 현재 Run은 헤더 또는 대시보드에서 선택
        </p>
      </div>

      <Alert>현재 적용 Run: {runId || "(없음)"}</Alert>

      <section>
        <h2 className="mb-3 font-medium">Run 목록</h2>
        <DataTable rows={runRows} />
      </section>

      <section>
        <label className="text-sm font-medium">상세 Run</label>
        <select
          className="mt-1 block rounded-md border px-3 py-2 text-sm"
          value={active}
          onChange={(e) => setPick(e.target.value)}
        >
          {(runsData?.runs || []).map((r) => (
            <option key={r.run_id} value={r.run_id}>
              {r.run_id}
            </option>
          ))}
        </select>
      </section>

      {active && (
        <>
          <section>
            <h2 className="mb-3 font-medium">단계 상태</h2>
            <DataTable rows={(data?.steps as Record<string, unknown>[]) || []} />
          </section>
          <section>
            <h2 className="mb-3 font-medium">모델 순위</h2>
            <DataTable rows={(data?.ranking as Record<string, unknown>[]) || []} />
          </section>
          <section>
            <h2 className="mb-3 font-medium">타겟 포착 4×4</h2>
            {(data?.test_matrices as { empty?: boolean })?.empty ? (
              <p className="text-sm text-muted-foreground">타겟 포착 분포 없음</p>
            ) : (
              <DualMatrices block={data?.test_matrices as never} />
            )}
          </section>
        </>
      )}
    </div>
  );
}
