"use client";

import { useEffect, useState } from "react";
import { AppLink } from "@/components/app-link";
import { useQuery } from "@tanstack/react-query";
import { apiGet, apiPost } from "@/lib/api";
import { formatDisplayValue } from "@/lib/utils";
import { useRun } from "@/components/run-context";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DataTable, MatrixTable } from "@/components/matrix-table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import type { ConfigMeta } from "@/lib/types";

export default function InferenceResultsPage() {
  const { runId } = useRun();
  const [view, setView] = useState<"grade" | "algo">("grade");
  const [grade, setGrade] = useState("(전체)");
  const [limit, setLimit] = useState(30);
  const [algo, setAlgo] = useState("");
  const [sortDesc, setSortDesc] = useState(true);
  const [exportMsg, setExportMsg] = useState("");

  const { data: meta } = useQuery({
    queryKey: ["configMeta"],
    queryFn: () => apiGet<ConfigMeta>("/api/config/meta"),
  });

  const { data: metaRes } = useQuery({
    queryKey: ["inferResults", runId],
    queryFn: () => apiGet<Record<string, unknown>>(`/api/inference/results?run_id=${runId}`),
    enabled: !!runId,
  });

  const { data: queue } = useQuery({
    queryKey: ["inferQueue", runId, grade, limit],
    queryFn: () =>
      apiGet<Record<string, unknown>>(
        `/api/inference/ops-queue?run_id=${runId}&grade=${encodeURIComponent(grade)}&limit=${limit}`,
      ),
    enabled: !!runId && view === "grade",
  });

  const available = (metaRes?.available as { algo: string }[]) || [];

  useEffect(() => {
    if (!algo && available.length) setAlgo(available[0].algo);
  }, [available, algo]);

  const { data: scores } = useQuery({
    queryKey: ["inferScores", algo, limit, sortDesc],
    queryFn: () =>
      apiGet<Record<string, unknown>>(
        `/api/inference/scores/${algo}?limit=${limit}&sort_desc=${sortDesc}`,
      ),
    enabled: view === "algo" && !!algo,
  });

  async function exportExcel() {
    const res = await apiPost<Record<string, unknown>>(`/api/inference/export?run_id=${runId}`);
    setExportMsg(
      `${res.row_count}건 · ${res.export_dir_hint}${res.xlsx_basename} (로컬 저장됨)`,
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">결과 확인</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          점수·점검 우선순위표 · Excel 내보내기 (미리보기 상한 적용)
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

          <Card>
            <CardHeader>
              <CardTitle>점검 우선순위표 Excel 내보내기</CardTitle>
              <p className="text-xs text-muted-foreground">
                시트: 전체 / 우선순위요약 / 4x4매트릭스 / 주A·주B·주C
              </p>
            </CardHeader>
            <CardContent className="space-y-2">
              <Button variant="secondary" onClick={exportExcel}>
                Excel·CSV 생성
              </Button>
              {exportMsg && <Alert variant="success">{exportMsg}</Alert>}
            </CardContent>
          </Card>

          <div className="flex gap-4 text-sm">
            <label className="flex items-center gap-2">
              <input
                type="radio"
                checked={view === "grade"}
                onChange={() => setView("grade")}
              />
              점검 우선순위 (주·보 4×4)
            </label>
            <label className="flex items-center gap-2">
              <input type="radio" checked={view === "algo"} onChange={() => setView("algo")} />
              알고리즘별 점수
            </label>
          </div>

          {view === "grade" ? (
            <Card>
              <CardContent className="space-y-4 pt-6">
                <p className="text-sm">
                  주 {(queue?.primary_label as string) || ""} / 보 {(queue?.aux_label as string) || ""}
                </p>
                <MatrixTable
                  matrix={queue?.matrix as never}
                  title="4×4 매트릭스 (점검 선정용)"
                  heatByPriority
                />
                <div className="flex gap-3">
                  <Select value={grade} onValueChange={setGrade}>
                    <SelectTrigger className="w-[140px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="(전체)">(전체)</SelectItem>
                      {["주A", "주B", "주C", "주D"].map((g) => (
                        <SelectItem key={g} value={g}>
                          {g}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Select value={String(limit)} onValueChange={(v) => setLimit(Number(v))}>
                    <SelectTrigger className="w-[100px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {[10, 30, 50, 100].map((n) => (
                        <SelectItem key={n} value={String(n)}>
                          {n}건
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <DataTable
                  rows={(queue?.preview_rows as Record<string, unknown>[]) || []}
                  columns={(queue?.preview_columns as string[]) || undefined}
                  maxHeight={360}
                />
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="space-y-4 pt-6">
                <Select value={algo} onValueChange={setAlgo}>
                  <SelectTrigger className="w-[200px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {available.map((a) => (
                      <SelectItem key={a.algo} value={a.algo}>
                        {meta?.algo_labels?.[a.algo] || a.algo}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <div className="grid gap-4 sm:grid-cols-4 text-sm">
                  <div>행 수: {formatDisplayValue(scores?.row_count ?? "-")}</div>
                  <div>평균: {formatDisplayValue(scores?.avg_score ?? "-")}</div>
                  <div>최고: {formatDisplayValue(scores?.max_score ?? "-")}</div>
                  <div>상위1% 추정: {formatDisplayValue(scores?.top1_est ?? "-")}</div>
                </div>
                {Array.isArray(scores?.crtr_ym) ? (
                  <DataTable rows={scores.crtr_ym as Record<string, unknown>[]} />
                ) : null}
                <label className="flex items-center gap-2 text-sm">
                  <Checkbox checked={sortDesc} onCheckedChange={(c) => setSortDesc(!!c)} />
                  위험도 점수 내림차순
                </label>
                <DataTable
                  rows={(scores?.preview_rows as Record<string, unknown>[]) || []}
                  columns={(scores?.preview_columns as string[]) || undefined}
                  maxHeight={360}
                />
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
