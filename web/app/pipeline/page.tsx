"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost, apiPut } from "@/lib/api";
import { cancelPipelineJob } from "@/lib/pipeline-cancel";
import { useRun } from "@/components/run-context";
import { DataSection } from "@/components/data-section";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { Alert } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DataTable } from "@/components/matrix-table";
import { LoadingSpinner } from "@/components/job-banner";
import { Skeleton } from "@/components/ui/skeleton";
import type { AlgoFamilyMeta, ConfigMeta } from "@/lib/types";

const PREP_IDS = new Set(["merge", "label", "preprocess", "leakage"]);
const TRAIN_IDS = new Set([
  "train",
  "feature_importance",
  "evaluate",
  "ranking",
  "report",
  "ops_queue",
]);

function asStringArray(v: unknown): string[] {
  return Array.isArray(v) ? v.map(String) : [];
}

type StepDialog = { sid: string; label: string } | null;

export default function PipelinePage() {
  const { runId, runs, loading: runsLoading } = useRun();
  const qc = useQueryClient();
  const [localRun, setLocalRun] = useState("");
  const [stepDialog, setStepDialog] = useState<StepDialog>(null);
  const [prepBatchOpen, setPrepBatchOpen] = useState(false);
  const [trainBatchOpen, setTrainBatchOpen] = useState(false);
  const [fullBatchOpen, setFullBatchOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [mode, setMode] = useState("time");
  const [splitForm, setSplitForm] = useState<Record<string, unknown>>({});
  const [formAlgos, setFormAlgos] = useState<string[]>([]);
  const [algoCollapsed, setAlgoCollapsed] = useState(true);

  useEffect(() => {
    if (runId) setLocalRun((prev) => prev || runId);
  }, [runId]);

  const activeRun = localRun || runId;

  useEffect(() => {
    setAlgoCollapsed(true);
  }, [activeRun]);

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
    refetchInterval: (q) =>
      q.state.data?.locked || q.state.data?.job_running ? 5000 : false,
  });

  const { data: stepsData, refetch: refetchSteps } = useQuery({
    queryKey: ["steps", activeRun],
    queryFn: () => apiGet<{ steps: Record<string, unknown>[] }>(`/api/runs/${activeRun}/steps`),
    enabled: !!activeRun,
    refetchInterval: () =>
      cfgData?.locked || cfgData?.job_running ? 5000 : false,
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
  const splitCommitted = Boolean(cfgData?.split_committed);
  const algorithmsCommitted = Boolean(cfgData?.algorithms_committed);
  const locked = Boolean(cfgData?.locked);
  const splitLocked = Boolean(cfgData?.split_locked ?? locked);
  const algorithmsEditable =
    cfgData?.algorithms_editable !== undefined
      ? Boolean(cfgData.algorithms_editable)
      : !locked;
  const prepComplete = Boolean(cfgData?.prep_complete);
  const jobRunning = Boolean(cfgData?.job_running);
  const stepStatus =
    cfgData?.step_status && typeof cfgData.step_status === "object"
      ? (cfgData.step_status as Record<string, string>)
      : {};
  const optsEdit = Boolean(cfgData?.opts_edit);
  const showSplitEditor = !splitCommitted || (optsEdit && !splitLocked);
  const showAlgoEditor = !algorithmsCommitted || (optsEdit && algorithmsEditable);
  const algoLabels = asStringArray(cfgData?.algo_labels);

  useEffect(() => {
    if (prepComplete && !algorithmsCommitted) {
      setAlgoCollapsed(false);
    }
  }, [prepComplete, algorithmsCommitted]);

  const trainSteps = Array.isArray(meta?.train_steps) ? meta!.train_steps : [];
  const stepRows = Array.isArray(stepsData?.steps) ? stepsData!.steps : [];
  const algoRegistry: AlgoFamilyMeta[] = Array.isArray(meta?.algorithm_registry)
    ? meta!.algorithm_registry!
    : [];
  const leakageFeatures = asStringArray(leakage?.all_features);
  const leakageSelectedDefault = asStringArray(leakage?.default_selected);

  const prepSteps = trainSteps.filter((s) => PREP_IDS.has(s.id));
  const trainEvalSteps = trainSteps.filter((s) => TRAIN_IDS.has(s.id));
  const prepStepIds = prepSteps.map((s) => s.id);
  const trainStepIds = trainEvalSteps.map((s) => s.id);

  const selectedRaw = asStringArray(cfgData?.selected_raw_files);
  const frozenRaw = asStringArray(cfgData?.frozen_raw_files);
  const hasTrainCsv = selectedRaw.length > 0;

  function familyHasSelection(family: string): boolean {
    const fam = algoRegistry.find((f) => f.family === family);
    if (!fam) return false;
    return fam.versions.some((v) => formAlgos.includes(v.algo_id));
  }

  function toggleFamily(family: string, checked: boolean) {
    const fam = algoRegistry.find((f) => f.family === family);
    if (!fam) return;
    const cur = new Set(formAlgos);
    if (checked) {
      for (const v of fam.versions) cur.add(v.algo_id);
    } else {
      for (const v of fam.versions) cur.delete(v.algo_id);
    }
    setFormAlgos([...cur]);
  }

  function toggleVersion(algoId: string, checked: boolean) {
    const cur = new Set(formAlgos);
    if (checked) cur.add(algoId);
    else cur.delete(algoId);
    setFormAlgos([...cur]);
  }

  useEffect(() => {
    if (!cfgData) return;
    if (split.mode) setMode(String(split.mode));
    setSplitForm({ ...split });
    setFormAlgos(asStringArray(config.algorithms));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cfgData]);

  async function saveSplitOptions() {
    setBusy(true);
    setMsg("");
    try {
      await apiPut(`/api/runs/${activeRun}/config`, {
        split: {
          mode,
          train_start: splitForm.train_start,
          train_end: splitForm.train_end,
          test_start: splitForm.test_start,
          test_end: splitForm.test_end,
          test_size: splitForm.test_size,
        },
        split_committed: true,
      });
      await refetch();
      setMsg("분할 옵션이 저장되었습니다.");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "분할 옵션 저장 실패");
    } finally {
      setBusy(false);
    }
  }

  async function saveAlgorithms() {
    if (formAlgos.length < 2) {
      setMsg("알고리즘을 2개 이상 선택하세요.");
      return;
    }
    setBusy(true);
    setMsg("");
    try {
      await apiPut(`/api/runs/${activeRun}/config`, {
        algorithms: formAlgos,
        algorithms_committed: true,
      });
      await refetch();
      setMsg("학습 알고리즘이 저장되었습니다.");
      setAlgoCollapsed(true);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "알고리즘 저장 실패");
    } finally {
      setBusy(false);
    }
  }

  async function startSteps(stepIds: string[]) {
    setStepDialog(null);
    setPrepBatchOpen(false);
    setTrainBatchOpen(false);
    setFullBatchOpen(false);
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
    if (!activeRun) return;
    setBusy(true);
    setMsg("");
    try {
      await cancelPipelineJob(activeRun, qc);
      await refetch();
      await refetchSteps();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "취소 실패");
    } finally {
      setBusy(false);
    }
  }

  function stepDisabled(stepId: string): boolean {
    if (jobRunning || busy) return true;
    if (PREP_IDS.has(stepId)) {
      if (!splitCommitted) return true;
      if (stepId === "merge" && !hasTrainCsv) return true;
      return false;
    }
    if (TRAIN_IDS.has(stepId)) {
      return !algorithmsCommitted || algos.length < 2;
    }
    return true;
  }

  function stepIcon(stepId: string) {
    const st = stepStatus[stepId];
    if (st === "succeeded") return "[OK]";
    if (st === "failed") return "[X]";
    if (st === "running") return "...";
    return "";
  }

  if (runsLoading) {
    return <Skeleton className="h-48 w-full" />;
  }

  if (!runs.length) {
    return (
      <Alert>
        발급된 Run이 없습니다. Run ID 발급 메뉴에서 Run을 먼저 만드세요.
      </Alert>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">학습 실행</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          데이터 가공(01~04) → 학습·평가(05~10). 추론은 별도 메뉴.
        </p>
      </div>

      <div>
        <Label>실행할 Run</Label>
        <div className="mt-1 flex min-w-0 flex-wrap items-center gap-3">
          <select
            className="block w-[220px] shrink-0 rounded-md border px-3 py-2 text-sm"
            value={activeRun}
            onChange={(e) => setLocalRun(e.target.value)}
          >
            {runs.map((r) => (
              <option key={r.run_id} value={r.run_id}>
                {r.run_id}
              </option>
            ))}
          </select>
          <Input
            readOnly
            tabIndex={-1}
            aria-label="작업내용"
            value={
              runs.find((r) => r.run_id === activeRun)?.work_content?.trim() ||
              (activeRun ? "(작업내용 없음)" : "")
            }
            className="min-w-[20rem] flex-1 cursor-default bg-muted/40 text-muted-foreground focus-visible:ring-0"
            onFocus={(e) => e.currentTarget.blur()}
          />
        </div>
      </div>

      {msg ? <Alert>{msg}</Alert> : null}
      {cfgError ? (
        <Alert variant="destructive">
          설정 조회 실패: {cfgErr instanceof Error ? cfgErr.message : "알 수 없는 오류"}
        </Alert>
      ) : null}

      {jobRunning ? (
        <PipelineLockAlert onAbandon={abandon} busy={busy} />
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>1. 데이터 가공 (01~04)</CardTitle>
          <p className="text-sm text-muted-foreground">
            학습 CSV 등록·선택 → Train/Test 분할 저장 → 01~04 실행. 01 시작 시 선택 CSV가 Run에
            동결됩니다.
          </p>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="min-w-0 rounded-md border p-4">
              <DataSection
                title="학습·평가 raw 데이터"
                caption="TLS4902R 레이아웃 CSV. data_root/raw. 사용할 파일 체크 → 선택 저장."
                kind="train"
                defaultCollapsed
                compactHeader
                statusLabel={hasTrainCsv ? "(선택 저장됨)" : ""}
                onSelectionSaved={() => void refetch()}
              />
            </div>

            <div className="min-w-0 rounded-md border p-4">
              <h3 className="text-sm font-semibold">
                Train/Test 분할 {splitLocked ? "(잠금)" : splitCommitted ? "(저장됨)" : ""}
              </h3>
              {!showSplitEditor ? (
                <div className="mt-2 space-y-2">
                  <p className="text-sm">{String(cfgData?.split_summary ?? "")}</p>
                  {!splitLocked ? (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        apiPost(`/api/runs/${activeRun}/pipeline/reopen`)
                          .then(() => refetch())
                          .catch((e) => setMsg(e instanceof Error ? e.message : "재오픈 실패"))
                      }
                    >
                      분할 옵션 수정
                    </Button>
                  ) : null}
                </div>
              ) : (
                <div className="mt-3 space-y-4">
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
                      {(["train_start", "train_end", "test_start", "test_end"] as const).map(
                        (k) => (
                          <div key={k}>
                            <Label>{k}</Label>
                            <Input
                              value={String(splitForm[k] ?? "")}
                              onChange={(e) => setSplitForm({ ...splitForm, [k]: e.target.value })}
                            />
                          </div>
                        ),
                      )}
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
                        value={String(splitForm.test_size ?? 0.3)}
                        onChange={(e) =>
                          setSplitForm({ ...splitForm, test_size: parseFloat(e.target.value) })
                        }
                      />
                    </div>
                  )}
                  <Button onClick={saveSplitOptions} disabled={busy}>
                    {busy ? <LoadingSpinner /> : null}
                    분할 옵션 저장
                  </Button>
                </div>
              )}
            </div>
          </div>

          {frozenRaw.length > 0 ? (
            <Alert>
              이 Run에 동결된 CSV ({frozenRaw.length}개):{" "}
              {frozenRaw.map((p) => p.split(/[/\\]/).pop() || p).join(", ")}
            </Alert>
          ) : null}

          {leakage?.available ? (
            <div className="rounded-md border p-4">
              <h3 className="text-sm font-semibold">누수 점검 대응 (FAIL/WARN)</h3>
              <p className="mb-3 mt-1 text-sm">판정: {String(leakage.verdict ?? "")}</p>
              <LeakageResume
                runId={activeRun}
                features={leakageFeatures}
                defaultSelected={leakageSelectedDefault}
                onDone={() => {
                  void refetch();
                  void refetchSteps();
                  void qc.invalidateQueries({ queryKey: ["activeJob"] });
                }}
              />
            </div>
          ) : null}

          {!splitCommitted ? (
            <Alert>분할 옵션을 저장한 뒤 01~04 단계를 실행할 수 있습니다.</Alert>
          ) : null}
          {!hasTrainCsv ? (
            <Alert variant="destructive">
              01 원본 통합을 실행하려면 위에서 CSV를 선택 저장하세요.
            </Alert>
          ) : null}

          <div>
            <h3 className="mb-2 text-sm font-medium">단계별 실행 (01~04)</h3>
            <div className="grid gap-2 sm:grid-cols-2">
              {prepSteps.map((step) => (
                <Button
                  key={step.id}
                  variant="outline"
                  className="justify-between"
                  disabled={stepDisabled(step.id)}
                  onClick={() => setStepDialog({ sid: step.id, label: step.label })}
                >
                  <span>{step.label}</span>
                  <span className="text-xs text-muted-foreground">{stepIcon(step.id)}</span>
                </Button>
              ))}
            </div>
            <Button
              className="mt-3"
              variant="secondary"
              disabled={!splitCommitted || !hasTrainCsv || jobRunning || busy}
              onClick={() => setPrepBatchOpen(true)}
            >
              01~04 일괄 실행
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>2. 학습·평가 (05~10)</CardTitle>
          <p className="text-sm text-muted-foreground">
            학습할 알고리즘(2개 이상) 저장 → 05~10 실행. 모델만 바꿀 때는 05부터 다시 실행하면
            됩니다.
          </p>
        </CardHeader>
        <CardContent className="space-y-6">
          {jobRunning ? (
            <PipelineLockAlert
              onAbandon={abandon}
              busy={busy}
              hint="학습·평가 Job 실행 중입니다."
            />
          ) : null}
          <div className="rounded-md border p-4">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0 flex-1">
                <h3 className="text-sm font-semibold">
                  학습 알고리즘{" "}
                  {!algorithmsEditable ? "(잠금)" : algorithmsCommitted ? "(저장됨)" : ""}
                </h3>
                {!algoCollapsed ? (
                  <p className="mt-1 text-xs text-muted-foreground">
                    종류 → 버전, 합계 2개 이상. 선택: {formAlgos.length}개
                  </p>
                ) : null}
              </div>
              <Button variant="outline" size="sm" onClick={() => setAlgoCollapsed(!algoCollapsed)}>
                {algoCollapsed ? "펼치기" : "접기"}
              </Button>
            </div>

            {algoCollapsed ? (
              <p className="mt-2 text-sm text-muted-foreground">
                {algorithmsCommitted && algoLabels.length
                  ? algoLabels.join(", ")
                  : formAlgos.length >= 2
                    ? `${formAlgos.length}개 선택 (미저장)`
                    : "2개 이상 선택 후 저장"}
              </p>
            ) : !showAlgoEditor ? (
              <div className="mt-3 space-y-2">
                <p className="text-sm">알고리즘: {algoLabels.join(", ") || "(없음)"}</p>
                {!algorithmsEditable ? null : (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      apiPost(`/api/runs/${activeRun}/pipeline/reopen`)
                        .then(() => {
                          setAlgoCollapsed(false);
                          return refetch();
                        })
                        .catch((e) => setMsg(e instanceof Error ? e.message : "재오픈 실패"))
                    }
                  >
                    학습 알고리즘 수정
                  </Button>
                )}
              </div>
            ) : (
              <div className="mt-3 space-y-4">
                <div className="space-y-3">
                  {(algoRegistry.length ? algoRegistry : []).map((fam) => {
                    const open = familyHasSelection(fam.family);
                    return (
                      <div key={fam.family} className="rounded-md border p-3">
                        <label className="flex items-center gap-2 text-sm font-medium">
                          <input
                            type="checkbox"
                            checked={open}
                            onChange={(e) => toggleFamily(fam.family, e.target.checked)}
                          />
                          {fam.label}
                        </label>
                        {open ? (
                          <div className="mt-2 ml-6 grid gap-2 sm:grid-cols-2">
                            {fam.versions.map((v) => (
                              <label key={v.algo_id} className="flex items-center gap-2 text-sm">
                                <input
                                  type="checkbox"
                                  checked={formAlgos.includes(v.algo_id)}
                                  onChange={(e) => toggleVersion(v.algo_id, e.target.checked)}
                                />
                                {v.label || v.version}
                              </label>
                            ))}
                          </div>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
                <Button onClick={saveAlgorithms} disabled={busy}>
                  {busy ? <LoadingSpinner /> : null}
                  학습 알고리즘 저장
                </Button>
              </div>
            )}
          </div>

          {!algorithmsCommitted ? (
            <Alert>
              {prepComplete
                ? "01~04가 완료되었습니다. 위에서 학습 알고리즘(2개 이상)을 선택·저장한 뒤 05~10을 실행하세요."
                : "학습 알고리즘을 저장한 뒤 05~10 단계를 실행할 수 있습니다."}
            </Alert>
          ) : null}

          <div>
            <h3 className="mb-2 text-sm font-medium">단계별 실행 (05~10)</h3>
            <div className="grid gap-2 sm:grid-cols-2">
              {trainEvalSteps.map((step) => (
                <Button
                  key={step.id}
                  variant="outline"
                  className="justify-between"
                  disabled={stepDisabled(step.id)}
                  onClick={() => setStepDialog({ sid: step.id, label: step.label })}
                >
                  <span>{step.label}</span>
                  <span className="text-xs text-muted-foreground">{stepIcon(step.id)}</span>
                </Button>
              ))}
            </div>
            <Button
              className="mt-3"
              variant="secondary"
              disabled={
                !algorithmsCommitted || algos.length < 2 || jobRunning || busy
              }
              onClick={() => setTrainBatchOpen(true)}
            >
              05~10 일괄 실행
            </Button>
          </div>
        </CardContent>
      </Card>

      <section>
        <h2 className="mb-3 text-lg font-medium">전체 일괄 실행 (01→10)</h2>
        <Button
          disabled={
            !splitCommitted ||
            !algorithmsCommitted ||
            algos.length < 2 ||
            !hasTrainCsv ||
            jobRunning ||
            busy
          }
          onClick={() => setFullBatchOpen(true)}
        >
          01→10 일괄 실행
        </Button>
      </section>

      <section>
        <h2 className="mb-3 text-lg font-medium">단계 상태</h2>
        {locked || jobRunning ? (
          <p className="mb-2 text-xs text-muted-foreground">
            {jobRunning ? "Job 실행 중 — 자동 갱신 (5초)" : "단계 진행 중 — 자동 갱신 (5초)"}
          </p>
        ) : null}
        <DataTable rows={stepRows} empty="아직 단계 기록이 없습니다." />
      </section>

      {stepDialog ? (
        <SimpleModal
          title={`${stepDialog.label} — 실행 방식`}
          onClose={() => setStepDialog(null)}
        >
          <div className="flex flex-col gap-2 sm:flex-row sm:justify-end">
            <Button disabled={busy} onClick={() => startSteps([stepDialog.sid])}>
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

      {prepBatchOpen ? (
        <SimpleModal title="01~04 일괄 실행 확인" onClose={() => setPrepBatchOpen(false)}>
          <p className="mb-4 text-sm">데이터 가공 4단계를 순서대로 실행합니다.</p>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setPrepBatchOpen(false)}>
              취소
            </Button>
            <Button disabled={busy} onClick={() => startSteps(prepStepIds)}>
              실행
            </Button>
          </div>
        </SimpleModal>
      ) : null}

      {trainBatchOpen ? (
        <SimpleModal title="05~10 일괄 실행 확인" onClose={() => setTrainBatchOpen(false)}>
          <p className="mb-4 text-sm">학습·평가 6단계를 순서대로 실행합니다. 시간이 오래 걸릴 수 있습니다.</p>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setTrainBatchOpen(false)}>
              취소
            </Button>
            <Button disabled={busy} onClick={() => startSteps(trainStepIds)}>
              실행
            </Button>
          </div>
        </SimpleModal>
      ) : null}

      {fullBatchOpen ? (
        <SimpleModal title="01~10 일괄 실행 확인" onClose={() => setFullBatchOpen(false)}>
          <p className="mb-4 text-sm text-amber-700">
            수 분~수 시간 소요될 수 있습니다. 절전을 끄고 진행하세요.
          </p>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setFullBatchOpen(false)}>
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

function PipelineLockAlert({
  onAbandon,
  busy,
  hint,
}: {
  onAbandon: () => void;
  busy?: boolean;
  hint?: string;
}) {
  return (
    <Alert>
      {hint ? `${hint} ` : ""}
      설정을 바꾸려면 「전체 작업 취소 후 설정 수정」을 사용하세요.
      <Button
        variant="outline"
        size="sm"
        className="ml-3"
        disabled={busy}
        onClick={onAbandon}
      >
        {busy ? <LoadingSpinner /> : null}
        전체 작업 취소 후 설정 수정
      </Button>
    </Alert>
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
  onDone,
}: {
  runId: string;
  features: string[];
  defaultSelected: string[];
  onDone: () => void;
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
            onDone();
          } finally {
            setBusy(false);
          }
        }}
      >
        제외 반영 후 01~04 재실행
      </Button>
    </div>
  );
}
