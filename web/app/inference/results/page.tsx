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
      meta?: { total?: number };
    };
    entity?: {
      all?: unknown;
      meta?: { total?: number };
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

export default function InferenceResultsPage() {
  const { runId } = useRun();
  const [caseTab, setCaseTab] = useState("primary_aux");

  const { data: metaRes } = useQuery({
    queryKey: ["inferResults", runId],
    queryFn: () => apiGet<Record<string, unknown>>(`/api/inference/results?run_id=${runId}`),
    enabled: !!runId,
  });

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["inferOps", runId],
    queryFn: ({ signal }) =>
      apiGet<Record<string, unknown>>(`/api/inference/ops-queue?run_id=${runId}`, {
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
    queryKey: ["inferOps", runId, "case", caseTab],
    queryFn: ({ signal }) =>
      apiGet<CaptureCase>(
        `/api/inference/ops-queue/cases/${caseTab}?run_id=${runId}`,
        { signal, timeoutMs: 90_000 },
      ),
    enabled: !!runId && !!activeMeta?.available,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">결과 확인</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          점검 우선순위(3케이스 · PK·엔티티). 산출물은{" "}
          <code className="text-xs">runs/&#123;run_id&#125;/algorithms/operations/</code>{" "}
          (<code className="text-xs">ops_queue_inference_pk/entity.*</code>)에 저장됩니다.
        </p>
      </div>

      {!runId ? (
        <Alert>Run을 선택하세요.</Alert>
      ) : metaRes?.empty ? (
        <Alert>
          {metaRes?.run_inference_missing
            ? "이 Run에는 추론 실행 기록이 없습니다 — "
            : "추론 점수 파일 없음 — "}
          <AppLink href="/inference/run/" className="underline">
            추론 실행
          </AppLink>
          후 이 Run 기준으로 표시됩니다.
        </Alert>
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle>알고리즘별 파일</CardTitle>
            </CardHeader>
            <CardContent>
              <DataTable rows={(metaRes?.available as Record<string, unknown>[]) || []} />
            </CardContent>
          </Card>

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

          {isLoading ? (
            <p className="text-sm text-muted-foreground">불러오는 중...</p>
          ) : isError ? (
            <Alert variant="destructive">
              {error instanceof ApiError
                ? error.message
                : "점검 우선순위 목록을 불러오지 못했습니다."}
            </Alert>
          ) : !hasData ? (
            <p className="text-sm text-muted-foreground">
              추론 완료 후 표시됩니다. 11 단계 산출물이 없으면 추론을 다시 실행하세요.
            </p>
          ) : (
            <>
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">선정 모델 (08 순위 · 이번 추론)</CardTitle>
                </CardHeader>
                <CardContent className="flex flex-wrap gap-4 text-sm">
                  <div>
                    <span className="text-muted-foreground">주 </span>
                    <span className="font-medium">
                      {roles.primary_label || roles.primary || "—"}
                    </span>
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
                          variant="inference"
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
        </>
      )}
    </div>
  );
}
