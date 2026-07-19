"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost } from "@/lib/api";
import { useRun } from "@/components/run-context";
import { Button } from "@/components/ui/button";
import { Input, Label, Textarea } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Alert } from "@/components/ui/alert";
import { DataTable } from "@/components/matrix-table";
import type { RunRow } from "@/lib/types";

export default function RunIssuePage() {
  const { runId, setRunId, refreshRuns } = useRun();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [operator, setOperator] = useState("");
  const [workContent, setWorkContent] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const { data } = useQuery({
    queryKey: ["runs", 30],
    queryFn: () => apiGet<{ runs: RunRow[] }>("/api/runs?limit=30"),
  });

  async function issue() {
    setError("");
    if (!operator.trim()) {
      setError("작업자를 입력하세요.");
      return;
    }
    if (!workContent.trim()) {
      setError("작업내용을 입력하세요.");
      return;
    }
    setSubmitting(true);
    try {
      const res = await apiPost<{ run_id: string }>("/api/runs", {
        operator: operator.trim(),
        work_content: workContent.trim(),
        note: note.trim(),
      });
      await setRunId(res.run_id);
      await refreshRuns();
      qc.invalidateQueries({ queryKey: ["runs"] });
      setOpen(false);
      setOperator("");
      setWorkContent("");
      setNote("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Run 발급 실패");
    } finally {
      setSubmitting(false);
    }
  }

  const rows =
    data?.runs.map((r) => ({
      run_id: r.run_id,
      발급시각: r.created_at?.slice(0, 19).replace("T", " ") || "",
      작업자: r.operator,
      작업내용: r.work_content,
      비고: r.note,
      상태: r.status,
    })) || [];

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Run ID 발급</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          학습·평가 Run을 발급합니다. 발급 후 「학습 실행」에서 사용하세요.
        </p>
      </div>

      <Alert>현재 적용 중 Run: {runId || "(없음)"}</Alert>

      <Button onClick={() => setOpen(true)}>새 Run ID 발급</Button>

      <section>
        <h2 className="mb-3 text-lg font-medium">최근 발급 목록</h2>
        {rows.length ? (
          <DataTable rows={rows} />
        ) : (
          <p className="text-sm text-muted-foreground">아직 발급된 Run이 없습니다.</p>
        )}
      </section>

      <Dialog open={open} onOpenChange={setOpen} modal>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>새 Run ID 발급</DialogTitle>
            <p className="text-sm text-muted-foreground">
              발급 시 현재 적용 Run으로 전환됩니다.
            </p>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="op">작업자 *</Label>
              <Input id="op" placeholder="예: 홍길동" value={operator} onChange={(e) => setOperator(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="wc">작업내용 *</Label>
              <Textarea
                id="wc"
                placeholder="예: 2025H2 재학습 · 시계열 분할"
                value={workContent}
                onChange={(e) => setWorkContent(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="note">비고</Label>
              <Textarea id="note" placeholder="선택 입력" value={note} onChange={(e) => setNote(e.target.value)} />
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              취소
            </Button>
            <Button onClick={issue} disabled={submitting}>
              {submitting ? "발급 중…" : "발급"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
