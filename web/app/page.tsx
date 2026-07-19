"use client";

import { AppLink } from "@/components/app-link";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import { useRun } from "@/components/run-context";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert } from "@/components/ui/alert";
import { DataTable, DualMatrices, MatrixTable } from "@/components/matrix-table";
import type { RunRow } from "@/lib/types";

export default function DashboardPage() {
  const { runId, setRunId, runs, refreshRuns, loading: runsLoading } = useRun();

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["dashboard", runId],
    queryFn: () => apiGet<Record<string, unknown>>(`/api/runs/${runId}/dashboard`),
    enabled: !!runId,
    placeholderData: (prev) => prev,
    staleTime: 30_000,
  });

  if (runsLoading) return <Skeleton className="h-48 w-full" />;

  if (!runs.length) {
    return (
      <Alert>
        Run 기록이 없습니다.{" "}
        <AppLink href="/run-issue/" className="text-primary underline">
          Run ID 발급
        </AppLink>
        으로 시작하세요.
      </Alert>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">대시보드</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          localhost 전용 · raw는 DB에 저장하지 않습니다.
        </p>
      </div>

      <section>
        <h2 className="mb-3 text-sm font-medium text-muted-foreground">Run 선택</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {runs.slice(0, 12).map((r: RunRow) => (
            <Button
              key={r.run_id}
              variant={r.run_id === runId ? "default" : "outline"}
              className="h-auto flex-col items-start px-4 py-3 text-left"
              onClick={() => setRunId(r.run_id)}
            >
              <span className="font-mono text-xs">{r.run_id}</span>
              <span className="mt-1 text-xs opacity-80">
                {r.operator || r.created_at?.slice(0, 19).replace("T", " ")}
              </span>
            </Button>
          ))}
        </div>
      </section>

      {!runId ? null : isLoading && !data ? (
        <Skeleton className="h-64 w-full" />
      ) : (
        <>
          {isFetching ? (
            <p className="text-xs text-muted-foreground">Run 데이터 불러오는 중…</p>
          ) : null}
          <Card>
            <CardHeader>
              <CardTitle>모델 평가</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {data?.ranking_empty ? (
                <Alert>
                  순위 없음 —{" "}
                  <AppLink href="/pipeline/" className="underline">
                    학습 실행
                  </AppLink>
                  에서 08 순위까지 완료하세요.
                </Alert>
              ) : (
                <>
                  <DataTable
                    rows={(data?.ranking as Record<string, unknown>[]) || []}
                    empty="순위 없음"
                  />
                  <p className="text-sm text-emerald-700 dark:text-emerald-400">
                    주 모델={String(data?.primary_label)} / 보조={String(data?.aux_label)}
                  </p>
                </>
              )}
              {(data?.test_matrices as { empty?: boolean })?.empty ? (
                <p className="text-sm text-muted-foreground">
                  타겟 포착 분포 없음 — 10 단계 완료 후 표시됩니다.
                </p>
              ) : (
                <DualMatrices block={data?.test_matrices as never} />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>추론</CardTitle>
              <p className="text-sm text-muted-foreground">
                상세·Excel은{" "}
                <AppLink href="/inference/results/" className="underline">
                  결과 확인
                </AppLink>
              </p>
            </CardHeader>
            <CardContent>
              {(data?.inference as { empty?: boolean })?.empty ? (
                <Alert>
                  {(data?.inference as { run_inference_missing?: boolean })?.run_inference_missing
                    ? "이 Run에는 추론 실행 기록이 없습니다 — "
                    : "추론 결과 없음 — "}
                  <AppLink href="/inference/run/" className="underline">
                    추론 실행
                  </AppLink>
                  후 이 Run 기준으로 표시됩니다.
                </Alert>
              ) : (
                <div className="space-y-3">
                  <p className="text-sm">
                    추론 {(data?.inference as { total?: number })?.total?.toLocaleString()}건 ·
                    주 {(data?.inference as { primary_label?: string })?.primary_label} / 보{" "}
                    {(data?.inference as { aux_label?: string })?.aux_label}
                  </p>
                  <MatrixTable
                    matrix={(data?.inference as { matrix?: never })?.matrix}
                    title="4×4 매트릭스 (점검 선정용)"
                    caption="라벨 미지 데이터 — 점검 우선순위 분포만 표시"
                    heatByPriority
                  />
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
