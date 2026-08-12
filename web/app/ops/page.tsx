"use client";

import { AppLink } from "@/components/app-link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiGet, ApiError } from "@/lib/api";
import { useRun } from "@/components/run-context";
import { Alert } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CaptureMatrixPanel, DataTable } from "@/components/matrix-table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

type CaptureCase = {
  id: string;
  title: string;
  row_axis: string;
  col_axis: string;
  available: boolean;
  reason?: string | null;
  loaded?: boolean;
  matrices?: {
    pk?: {
      all?: unknown;
      positive?: unknown;
      meta?: { total?: number; positive?: number };
      positive_in_abc_pct?: number | null;
    };
    entity?: {
      all?: unknown;
      positive?: unknown;
      meta?: { total?: number; positive?: number };
      positive_in_abc_pct?: number | null;
    };
  };
  summary?: Record<string, unknown>[];
};

type Roles = {
  primary?: string;
  aux?: string;
  reference?: string | null;
  primary_label?: string | null;
  aux_label?: string | null;
  reference_label?: string | null;
};

export default function OpsPage() {
  const { runId } = useRun();
  const [caseTab, setCaseTab] = useState("primary_aux");

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["ops", runId],
    queryFn: ({ signal }) =>
      apiGet<Record<string, unknown>>(`/api/runs/${runId}/ops-queue`, {
        signal,
        timeoutMs: 60_000,
      }),
    enabled: !!runId,
  });

  const bandHelp = (data?.band_help as Record<string, string>) || {};
  const roles = (data?.roles as Roles) || {};
  const cases = (data?.cases as CaptureCase[]) || [];
  const hasData = cases.some((c) => c.available);

  const activeMeta = cases.find((c) => c.id === caseTab);
  const {
    data: caseDetail,
    isLoading: caseLoading,
    isError: caseError,
    error: caseErr,
  } = useQuery({
    queryKey: ["ops", runId, "case", caseTab],
    queryFn: ({ signal }) =>
      apiGet<CaptureCase>(`/api/runs/${runId}/ops-queue/cases/${caseTab}`, {
        signal,
        timeoutMs: 90_000,
      }),
    enabled: !!runId && !!activeMeta?.available,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">타겟 포착 분포</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Test 4×4 조회 전용 — 재실행은{" "}
          <AppLink href="/pipeline/" className="underline">
            학습 실행
          </AppLink>{" "}
          10 단계.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-4">
        {(["주A", "주B", "주C", "주D"] as const).map((g) => (
          <div key={g} className="rounded-lg border p-3" title={bandHelp[g]}>
            <p className="text-xs text-muted-foreground">{g}</p>
            <p className="text-sm font-medium">
              {g === "주A" && "상위1%"}
              {g === "주B" && "1~5%"}
              {g === "주C" && "5~10%"}
              {g === "주D" && ">10%"}
            </p>
          </div>
        ))}
      </div>

      {!runId ? (
        <Alert>Run을 선택하세요.</Alert>
      ) : isLoading ? (
        <p className="text-sm text-muted-foreground">불러오는 중...</p>
      ) : isError ? (
        <Alert variant="destructive">
          {error instanceof ApiError ? error.message : "타겟 포착 목록을 불러오지 못했습니다."}
        </Alert>
      ) : !hasData ? (
        <p className="text-sm text-muted-foreground">10 단계를 실행하면 표시됩니다.</p>
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">선정 모델 (08 순위)</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-4 text-sm">
              <div>
                <span className="text-muted-foreground">주 </span>
                <span className="font-medium">{roles.primary_label || roles.primary || "—"}</span>
              </div>
              <div>
                <span className="text-muted-foreground">보 </span>
                <span className="font-medium">{roles.aux_label || roles.aux || "—"}</span>
              </div>
              <div>
                <span className="text-muted-foreground">참 </span>
                <span className="font-medium">
                  {roles.reference_label || roles.reference || "—"}
                </span>
              </div>
            </CardContent>
          </Card>

          <Tabs value={caseTab} onValueChange={setCaseTab}>
            <TabsList>
              {cases.map((c) => (
                <TabsTrigger key={c.id} value={c.id}>
                  {c.title}
                </TabsTrigger>
              ))}
            </TabsList>
            {cases.map((c) => (
              <TabsContent key={c.id} value={c.id} className="space-y-4">
                {!c.available ? (
                  <p className="text-sm text-muted-foreground">{c.reason || "해당 없음"}</p>
                ) : caseTab !== c.id ? null : caseLoading ? (
                  <p className="text-sm text-muted-foreground">매트릭스 불러오는 중...</p>
                ) : caseError ? (
                  <Alert variant="destructive">
                    {caseErr instanceof ApiError
                      ? caseErr.message
                      : "케이스 데이터를 불러오지 못했습니다."}
                  </Alert>
                ) : caseDetail && !caseDetail.available ? (
                  <p className="text-sm text-muted-foreground">
                    {caseDetail.reason || "해당 없음"}
                  </p>
                ) : (
                  <>
                    <CaptureMatrixPanel
                      rowAxis={caseDetail?.row_axis || c.row_axis}
                      colAxis={caseDetail?.col_axis || c.col_axis}
                      pk={caseDetail?.matrices?.pk as never}
                      entity={caseDetail?.matrices?.entity as never}
                    />
                    <details className="text-sm">
                      <summary className="cursor-pointer font-medium">
                        조합별 건수·우선순위 (상세) — {c.title}
                      </summary>
                      <div className="mt-3">
                        <DataTable rows={caseDetail?.summary || []} />
                      </div>
                    </details>
                  </>
                )}
              </TabsContent>
            ))}
          </Tabs>
        </>
      )}

      <Alert>재실행은 「학습 실행」10 단계에서 하세요.</Alert>
    </div>
  );
}
