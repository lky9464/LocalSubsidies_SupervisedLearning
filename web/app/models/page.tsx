"use client";

import { AppLink } from "@/components/app-link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import { useRun } from "@/components/run-context";
import { Alert } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DataTable, DualMatrices } from "@/components/matrix-table";
import { ModelRadarChart } from "@/components/radar-chart";
import { Skeleton } from "@/components/ui/skeleton";
import { Checkbox } from "@/components/ui/checkbox";

export default function ModelsPage() {
  const { runId } = useRun();
  const [metrics, setMetrics] = useState<string[]>([
    "PR-AUC",
    "상위1%리프트",
    "상위1%양성포착",
    "F1",
  ]);

  const { data, isLoading } = useQuery({
    queryKey: ["models", runId, metrics.join(",")],
    queryFn: () =>
      apiGet<Record<string, unknown>>(
        `/api/runs/${runId}/models?metrics=${encodeURIComponent(metrics.join(","))}`,
      ),
    enabled: !!runId,
  });

  const available = (data?.radar_metrics_available as string[]) || [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">모델 비교·평가</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          결과 조회용 — 재실행은{" "}
          <AppLink href="/pipeline/" className="underline">
            학습 실행
          </AppLink>{" "}
          07/08에서.
        </p>
      </div>

      {!runId ? (
        <Alert>Run을 선택하세요.</Alert>
      ) : isLoading ? (
        <Skeleton className="h-64" />
      ) : data?.empty ? (
        <Alert>모델 순위 없음 — 07·08 단계를 완료하세요.</Alert>
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle>모델 순위</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <details className="text-sm">
                <summary className="cursor-pointer font-medium">지표 설명</summary>
                <ul className="mt-2 list-disc space-y-2 pl-5 text-muted-foreground">
                  {Object.entries((data?.metric_help as Record<string, string>) || {}).map(
                    ([k, v]) => (
                      <li key={k}>
                        <strong>{k}</strong>: {v}
                      </li>
                    ),
                  )}
                </ul>
              </details>
              <DataTable rows={(data?.ranking as Record<string, unknown>[]) || []} />
              <p className="text-xs text-muted-foreground">
                순위: PR-AUC → 상위1% 리프트 → F1 · 1위=주, 2위=보
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>모델별 지표비교</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap gap-3">
                {available.map((m) => (
                  <label key={m} className="flex items-center gap-2 text-sm">
                    <Checkbox
                      checked={metrics.includes(m)}
                      onCheckedChange={(c) =>
                        setMetrics(c ? [...metrics, m] : metrics.filter((x) => x !== m))
                      }
                    />
                    {m}
                  </label>
                ))}
              </div>
              {metrics.length < 3 && (
                <Alert>표시할 지표를 3개 이상 선택하세요.</Alert>
              )}
              <ModelRadarChart
                metrics={((data?.radar as { metrics?: string[] })?.metrics) || metrics}
                series={((data?.radar as { series?: never })?.series) || []}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Test 4×4</CardTitle>
            </CardHeader>
            <CardContent>
              {(data?.test_matrices as { empty?: boolean })?.empty ? (
                <Alert>07·10 완료 후 표시됩니다.</Alert>
              ) : (
                <DualMatrices block={data?.test_matrices as never} />
              )}
            </CardContent>
          </Card>
        </>
      )}

      <Alert>
        재실행은 「학습 실행」07(평가·점수)·08(모델 순위)에서 하세요.
      </Alert>
    </div>
  );
}
