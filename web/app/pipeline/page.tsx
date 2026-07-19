"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { AppLink } from "@/components/app-link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost, apiPut } from "@/lib/api";
import { useRun } from "@/components/run-context";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { Alert } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DataTable } from "@/components/matrix-table";
import { LoadingSpinner } from "@/components/job-banner";
import { Skeleton } from "@/components/ui/skeleton";
import type { ConfigMeta } from "@/lib/types";

function asStringArray(v: unknown): string[] {
  return Array.isArray(v) ? v.map(String) : [];
}

type StepDialog = { sid: string; label: string } | null;

export default function PipelinePage() {
  const { runId, runs, loading: runsLoading } = useRun();
  const qc = useQueryClient();
  const [localRun, setLocalRun] = useState("");
  const [stepDialog, setStepDialog] = useState<StepDialog>(null);
  const [batchOpen, setBatchOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [mode, setMode] = useState("time");
  const [form, setForm] = useState<Record<string, unknown>>({ algorithms: [] as string[] });

  useEffect(() => {
    if (runId) setLocalRun((prev) => prev || runId);
  }, [runId]);

  const activeRun = localRun || runId;

  const { data: meta } = useQuery({
    queryKey: ["configMeta"],
    queryFn: () => apiGet<ConfigMeta>("/api/config/meta"),
    staleTime: 60_000,
  });

  const {
    data: cfgData,
    refetch,
    isError: cfgError,
    error: cfgErr,
  } = useQuery({
    queryKey: ["runConfig", activeRun],
    queryFn: () => apiGet<Record<string, unknown>>(`/api/runs/${activeRun}/config`),
    enabled: !!activeRun,
    refetchInterval: (q) => (q.state.data?.locked ? 5000 : false),
  });

  const { data: stepsData, refetch: refetchSteps } = useQuery({
    queryKey: ["steps", activeRun],
    queryFn: () => apiGet<{ steps: Record<string, unknown>[] }>(`/api/runs/${activeRun}/steps`),
    enabled: !!activeRun,
    refetchInterval: (q) => {
      // use this query's sibling via locked flag on config
      void q;
      return cfgData?.locked ? 5000 : false;
    },
  });

  const { data: leakage } = useQuery({
    queryKey: ["leakage", activeRun],
    queryFn: () => apiGet<Record<string, unknown>>(`/api/runs/${activeRun}/leakage`),
    enabled: !!activeRun,
    staleTime: 15_000,
  });

  const config = useMemo(
    () => (cfgData?.config as Record<string, unknown>) || {},
    [cfgData],
  );
  const split = useMemo(
    () => (config.split as Record<string, unknown>) || {},
    [config],
  );
  const algos = asStringArray(config.algorithms);
  const committed = Boolean(cfgData?.committed);
  const locked = Boolean(cfgData?.locked);
  const stepStatus =
    cfgData?.step_status && typeof cfgData.step_status === "object"
      ? (cfgData.step_status as Record<string, string>)
      : {};
  const showEditor = !committed || Boolean(cfgData?.opts_edit && !locked);
  const formAlgos = asStringArray(form.algorithms);
  const algoLabels = asStringArray(cfgData?.algo_labels);
  const trainSteps = Array.isArray(meta?.train_steps) ? meta!.train_steps : [];
  const stepRows = Array.isArray(stepsData?.steps) ? stepsData!.steps : [];
  const metaAlgos = asStringArray(meta?.algorithms);
  const leakageFeatures = asStringArray(leakage?.all_features);
  const leakageSelectedDefault = asStringArray(leakage?.default_selected);

  useEffect(() => {
    if (!cfgData) return;
    if (split.mode) setMode(String(split.mode));
    setForm({ ...split, algorithms: asStringArray(config.algorithms) });
    // intentionally only when cfgData identity changes (fetch result)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cfgData]);

  async function saveOptions() {
    if (formAlgos.length < 2) {
      setMsg("알고리즘을 2개 이상 선택하세요.");
      return;
    }
    setBusy(true);
    setMsg("");
    try {
      await apiPut(`/api/runs/${activeRun}/config`, {
        split: {
          mode,
          train_start: form.train_start,
          train_end: form.train_end,
          test_start: form.test_start,
          test_end: form.test_end,
          test_size: form.test_size,
        },
        algorithms: formAlgos,
        options_committed: true,
      });
      await refetch();
      setMsg("학습 옵션이 저장되었습니다.");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "옵션 저장 실패");
    } finally {
      setBusy(false);
    }
  }

  async function startSteps(stepIds: string[]) {
    setStepDialog(null);
    setBatchOpen(false);
    setBusy(true);
    setMsg("");
    try {
      await apiPost(`/api/runs/${activeRun}/pipeline/start`, { step_ids: stepIds });
      await refetch();
      await refetchSteps();
      void qc.invalidateQueries({ queryKey: ["activeJob"] });
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "단계 시작 실패");
    } finally {
      setBusy(false);
    }
  }

  async function abandon() {
    try {
      await apiPost(`/api/runs/${activeRun}/pipeline/abandon`, {
        abandon: true,
        opts_edit: true,
      });
      await refetch();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "취소 실패");
    }
  }

  if (runsLoading) {
    return <Skeleton className="h-48 w-full" />;
  }

  if (!runs.length) {
    return (
      <Alert>
        발급된 Run이 없습니다.{" "}
        <AppLink href="/run-issue/" className="underline">
          Run ID 발급
        </AppLink>
      </Alert>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">학습 실행</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          01~10 순차 실행 (추론은 별도 메뉴). Run 발급은 「Run ID 발급」에서.
        </p>
      </div>

      <div>
        <Label>실행할 Run</Label>
        <select
          className="mt-1 block rounded-md border px-3 py-2 text-sm"
          value={activeRun}
          onChange={(e) => setLocalRun(e.target.value)}
        >
          {runs.map((r) => (
            <option key={r.run_id} value={r.run_id}>
              {r.run_id}
            </option>
          ))}
        </select>
      </div>

      {msg ? <Alert>{msg}</Alert> : null}
      {cfgError ? (
        <Alert variant="destructive">
          설정 조회 실패: {cfgErr instanceof Error ? cfgErr.message : "알 수 없는 오류"}
        </Alert>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>
            학습 옵션 {locked ? "(잠금)" : committed ? "(저장됨)" : ""}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {!showEditor ? (
            <>
              <p className="text-sm">{String(cfgData?.split_summary ?? "")}</p>
              <p className="text-sm">알고리즘: {algoLabels.join(", ") || "(없음)"}</p>
              {locked ? (
                <>
                  <p className="text-xs text-muted-foreground">
                    1번 단계 시작 후~파이프라인 완료 전에는 변경할 수 없습니다.
                  </p>
                  <Button variant="outline" onClick={abandon}>
                    전체 작업 취소 후 설정 수정
                  </Button>
                </>
              ) : (
                <Button
                  variant="outline"
                  onClick={() =>
                    apiPost(`/api/runs/${activeRun}/pipeline/reopen`)
                      .then(() => refetch())
                      .catch((e) => setMsg(e instanceof Error ? e.message : "재오픈 실패"))
                  }
                >
                  학습 옵션 수정
                </Button>
              )}
            </>
          ) : (
            <div className="space-y-4 rounded-md border p-4">
              <div className="flex gap-4">
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="radio"
                    name="split-mode"
                    checked={mode === "time"}
                    onChange={() => setMode("time")}
                  />
                  기간(time)
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="radio"
                    name="split-mode"
                    checked={mode === "random"}
                    onChange={() => setMode("random")}
                  />
                  랜덤(random)
                </label>
              </div>
              {mode === "time" ? (
                <div className="grid gap-3 sm:grid-cols-2">
                  {(["train_start", "train_end", "test_start", "test_end"] as const).map((k) => (
                    <div key={k}>
                      <Label>{k}</Label>
                      <Input
                        value={String(form[k] ?? "")}
                        onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                      />
                    </div>
                  ))}
                  {cfgData?.warn_test_share ? (
                    <Alert className="sm:col-span-2">{String(cfgData.warn_test_share)}</Alert>
                  ) : null}
                </div>
              ) : (
                <div>
                  <Label>Test 비중</Label>
                  <Input
                    type="number"
                    step="0.05"
                    min="0.1"
                    max="0.5"
                    value={String(form.test_size ?? 0.3)}
                    onChange={(e) => setForm({ ...form, test_size: parseFloat(e.target.value) })}
                  />
                </div>
              )}
              <div>
                <Label>학습 알고리즘 (2개 이상)</Label>
                <div className="mt-2 grid gap-2 sm:grid-cols-2">
                  {metaAlgos.map((a) => (
                    <label key={a} className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={formAlgos.includes(a)}
                        onChange={(e) => {
                          const cur = new Set(formAlgos);
                          if (e.target.checked) cur.add(a);
                          else cur.delete(a);
                          setForm({ ...form, algorithms: [...cur] });
                        }}
                      />
                      {(meta?.algo_labels && meta.algo_labels[a]) || a}
                    </label>
                  ))}
                </div>
              </div>
              <Button onClick={saveOptions} disabled={busy}>
                {busy ? <LoadingSpinner /> : null}
                학습 옵션 저장
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {leakage?.available ? (
        <Card>
          <CardHeader>
            <CardTitle>누수 점검 대응 (FAIL/WARN)</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="mb-3 text-sm">판정: {String(leakage.verdict ?? "")}</p>
            <LeakageResume
              runId={activeRun}
              features={leakageFeatures}
              defaultSelected={leakageSelectedDefault}
            />
          </CardContent>
        </Card>
      ) : null}

      {!committed && !cfgData?.config_exists ? (
        <Alert>먼저 「학습 옵션 저장」을 완료한 뒤 단계를 실행하세요.</Alert>
      ) : null}

      <section>
        <h2 className="mb-3 text-lg font-medium">단계별 실행</h2>
        <div className="grid gap-2 sm:grid-cols-2">
          {trainSteps.map((step) => {
            const st = stepStatus[step.id];
            const icon =
              st === "succeeded" ? "[OK]" : st === "failed" ? "[X]" : st === "running" ? "..." : "";
            return (
              <Button
                key={step.id}
                variant="outline"
                className="justify-between"
                disabled={!committed || locked || busy}
                onClick={() => setStepDialog({ sid: step.id, label: step.label })}
              >
                <span>{step.label}</span>
                <span className="text-xs text-muted-foreground">{icon}</span>
              </Button>
            );
          })}
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-lg font-medium">일괄 실행 (01→10)</h2>
        <Button
          disabled={!committed || algos.length < 2 || busy}
          onClick={() => setBatchOpen(true)}
        >
          01→10 일괄 실행
        </Button>
      </section>

      <section>
        <h2 className="mb-3 text-lg font-medium">단계 상태</h2>
        {locked ? (
          <p className="mb-2 text-xs text-muted-foreground">자동 갱신 중 (5초)</p>
        ) : null}
        <DataTable rows={stepRows} empty="아직 단계 기록이 없습니다." />
      </section>

      {stepDialog ? (
        <SimpleModal
          title={`${stepDialog.label} — 실행 방식`}
          onClose={() => setStepDialog(null)}
        >
          <div className="flex flex-col gap-2 sm:flex-row sm:justify-end">
            <Button
              disabled={busy}
              onClick={() => startSteps([stepDialog.sid])}
            >
              현재 단계만 실행
            </Button>
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() => {
                const ids = trainSteps.map((s) => s.id);
                const idx = ids.indexOf(stepDialog.sid);
                startSteps(ids.slice(Math.max(0, idx)));
              }}
            >
              현재 단계부터 마지막까지 실행
            </Button>
          </div>
        </SimpleModal>
      ) : null}

      {batchOpen ? (
        <SimpleModal title="일괄 실행 확인" onClose={() => setBatchOpen(false)}>
          <p className="mb-4 text-sm text-amber-700">
            수 분~수 시간 소요될 수 있습니다. 절전을 끄고 진행하세요.
          </p>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setBatchOpen(false)}>
              취소
            </Button>
            <Button
              disabled={busy}
              onClick={() => startSteps(trainSteps.map((s) => s.id))}
            >
              실행
            </Button>
          </div>
        </SimpleModal>
      ) : null}
    </div>
  );
}

function SimpleModal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div
        role="dialog"
        aria-modal="true"
        className="w-full max-w-lg rounded-lg border bg-background p-6 shadow-lg"
      >
        <div className="mb-4 flex items-start justify-between gap-3">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button
            type="button"
            className="text-sm text-muted-foreground hover:text-foreground"
            onClick={onClose}
          >
            닫기
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

function LeakageResume({
  runId,
  features,
  defaultSelected,
}: {
  runId: string;
  features: string[];
  defaultSelected: string[];
}) {
  const [selected, setSelected] = useState<string[]>(() => [...defaultSelected]);
  const [busy, setBusy] = useState(false);
  const defaultsKey = defaultSelected.join("|");

  useEffect(() => {
    setSelected(defaultsKey ? defaultsKey.split("|") : []);
  }, [defaultsKey]);

  return (
    <div className="space-y-3">
      <pre className="max-h-32 overflow-auto rounded bg-muted p-2 text-xs">
        {features.slice(0, 40).join("\n")}
      </pre>
      <div className="max-h-40 space-y-1 overflow-auto">
        {features.map((f) => (
          <label key={f} className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={selected.includes(f)}
              onChange={(e) =>
                setSelected(
                  e.target.checked ? [...selected, f] : selected.filter((x) => x !== f),
                )
              }
            />
            {f}
          </label>
        ))}
      </div>
      <Button
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          try {
            await apiPost(`/api/runs/${runId}/leakage/resume`, { features: selected });
          } finally {
            setBusy(false);
          }
        }}
      >
        제외 반영 후 03부터 재개
      </Button>
    </div>
  );
}
