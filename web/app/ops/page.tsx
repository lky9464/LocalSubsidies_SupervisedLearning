"use client";

import { AppLink } from "@/components/app-link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import { useRun } from "@/components/run-context";
import { Alert } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DualMatrices, DataTable } from "@/components/matrix-table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export default function OpsPage() {
  const { runId } = useRun();
  const [grade, setGrade] = useState("(전체)");
  const [limit, setLimit] = useState(30);

  const { data, isLoading } = useQuery({
    queryKey: ["ops", runId, grade, limit],
    queryFn: () =>
      apiGet<Record<string, unknown>>(
        `/api/runs/${runId}/ops-queue?grade=${encodeURIComponent(grade)}&limit=${limit}`,
      ),
    enabled: !!runId,
  });

  const bandHelp = (data?.band_help as Record<string, string>) || {};
  const matrices = data?.test_matrices as { empty?: boolean } | undefined;

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
      ) : !matrices || matrices.empty ? (
        <p className="text-sm text-muted-foreground">10 단계를 실행하면 표시됩니다.</p>
      ) : (
        <>
          <DualMatrices block={data?.test_matrices as never} />

          <Card>
            <CardHeader>
              <CardTitle>조합별 건수·우선순위 (상세)</CardTitle>
            </CardHeader>
            <CardContent>
              <DataTable rows={(data?.summary as Record<string, unknown>[]) || []} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>미리보기</CardTitle>
              <p className="text-xs text-muted-foreground">
                미리보기만 표시 · 전체는 Excel/로컬 파일
              </p>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap gap-3">
                <Select value={grade} onValueChange={setGrade}>
                  <SelectTrigger className="w-[140px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="(전체)">(전체)</SelectItem>
                    {((data?.primary_labels as string[]) || []).map((g) => (
                      <SelectItem key={g} value={g}>
                        {g}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Select value={String(limit)} onValueChange={(v) => setLimit(Number(v))}>
                  <SelectTrigger className="w-[120px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {((data?.preview_options as number[]) || [10, 30, 50, 100]).map((n) => (
                      <SelectItem key={n} value={String(n)}>
                        {n}건
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <DataTable
                rows={(data?.preview as Record<string, unknown>[]) || []}
                maxHeight={360}
              />
            </CardContent>
          </Card>
        </>
      )}

      <Alert>재실행은 「학습 실행」10 단계에서 하세요.</Alert>
    </div>
  );
}
