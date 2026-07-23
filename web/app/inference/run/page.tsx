"use client";

import { useEffect, useState, type ReactNode } from "react";
import { AppLink } from "@/components/app-link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost } from "@/lib/api";
import { useRun } from "@/components/run-context";
import { DataSection } from "@/components/data-section";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LoadingSpinner } from "@/components/loading-spinner";
import type { ConfigMeta } from "@/lib/types";

type TrainedPayload = {
  train_succeeded?: boolean;
  trained?: string[];
  trained_labels?: Record<string, string>;
  primary?: string | null;
  aux?: string | null;
  primary_label?: string | null;
  aux_label?: string | null;
  defaults?: string[];
};

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
      <div role="dialog" aria-modal="true" className="w-full max-w-lg rounded-lg border bg-background p-6 shadow-lg">
        <div className="mb-4 flex items-start justify-between gap-3">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button type="button" className="text-sm text-muted-foreground" onClick={onClose}>
            닫기
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export default function InferenceRunPage() {
  const { runId } = useRun();
  const qc = useQueryClient();
  const [selected, setSelected] = useState<string[]>([]);
  const [defaultsKey, setDefaultsKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [missingOpen, setMissingOpen] = useState(false);
  const [missingLabels, setMissingLabels] = useState<string[]>([]);

  const { data: prereq, refetch: refetchPrereq } = useQuery({
    queryKey: ["inferPrereq"],
    queryFn: () =>
      apiGet<{
        has_data: boolean;
        file_count?: number;
        selected_files?: string[];
        message?: string;
      }>("/api/inference/prereq"),
  });

  const { data: meta } = useQuery({
    queryKey: ["configMeta"],
    queryFn: () => apiGet<ConfigMeta>("/api/config/meta"),
  });

  const { data: trainedInfo } = useQuery({
    queryKey: ["inferTrained", runId],
    queryFn: () => apiGet<TrainedPayload>(`/api/inference/trained?run_id=${runId}`),
    enabled: !!runId,
  });

  const trainedSet = new Set(trainedInfo?.trained || []);
  const labels = meta?.algo_labels || {};
  const hasInferData = Boolean(prereq?.has_data);

  useEffect(() => {
    if (!runId || !trainedInfo) return;
    const nextDefaults = (trainedInfo.defaults || []).filter((a) =>
      (trainedInfo.trained || []).includes(a),
    );
    const key = `${runId}:${nextDefaults.join(",")}`;
    if (key === defaultsKey) return;
    setDefaultsKey(key);
    setSelected(nextDefaults);
  }, [runId, trainedInfo, defaultsKey]);

  function labelOf(algo: string) {
    return labels[algo] || trainedInfo?.trained_labels?.[algo] || algo;
  }

  function roleHint(algo: string): string | null {
    if (algo === trainedInfo?.primary) return "주모델";
    if (algo === trainedInfo?.aux) return "보조모델";
    return null;
  }

  async function startInference() {
    setBusy(true);
    setErr("");
    try {
      const extra: string[] = [];
      selected.forEach((a) => {
        extra.push("--algo", a);
      });
      await apiPost("/api/inference/run", {
        run_id: runId,
        step_ids: ["inference"],
        extra_args_by_step: { inference: extra },
      });
      qc.invalidateQueries({ queryKey: ["activeJob"] });
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  function run() {
    if (!runId) {
      setErr("Run ID가 없습니다. 「Run ID 발급」에서 Run을 선택하세요.");
      return;
    }
    if (!hasInferData) {
      setErr("추론 CSV를 선택 저장한 뒤 실행하세요.");
      return;
    }
    const allowed = selected.filter((a) => trainedSet.has(a));
    if (!allowed.length) {
      setErr("이 Run에서 학습된 알고리즘을 1개 이상 선택하세요.");
      return;
    }
    const missing = selected.filter((a) => !trainedSet.has(a));
    if (missing.length) {
      setMissingLabels(missing.map(labelOf));
      setMissingOpen(true);
      return;
    }
    void startInference();
  }

  const hasTrained = trainedSet.size > 0;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">추론 실행</h1>
        <p className="mt-1 text-sm text-muted-foreground">Run: {runId || "(없음)"}</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>추론 raw 데이터</CardTitle>
        </CardHeader>
        <CardContent>
          <DataSection
            title="추론용 CSV"
            caption="동일 TLS4902R 레이아웃. data_root/raw_inference. 체크 → 선택 저장 → 추론 실행."
            kind="inference"
            defaultCollapsed={hasInferData}
            onSelectionSaved={() => void refetchPrereq()}
          />
          {hasInferData && (prereq?.selected_files?.length || 0) > 0 ? (
            <Alert className="mt-4">
              선택 저장됨 ({prereq!.selected_files!.length}개):{" "}
              {prereq!.selected_files!.join(", ")}
            </Alert>
          ) : (
            <Alert variant="destructive" className="mt-4">
              {prereq?.message || "추론 CSV를 등록·선택 저장하세요."}
            </Alert>
          )}
        </CardContent>
      </Card>

      <Alert>
        현재 Run에서 학습된 알고리즘만 선택할 수 있습니다. 기본값은 평가순위 주모델(1위)·보조모델(2위)입니다.
      </Alert>

      {!trainedInfo?.train_succeeded || !hasTrained ? (
        <Alert variant="destructive">
          이 Run에서 학습된 모델이 없습니다.{" "}
          <AppLink href="/pipeline/" className="underline">
            학습 실행
          </AppLink>
          에서 알고리즘을 학습한 뒤 추론하세요.
        </Alert>
      ) : trainedInfo.primary || trainedInfo.aux ? (
        <p className="text-sm text-muted-foreground">
          기본 선택: 주 {trainedInfo.primary_label || trainedInfo.primary || "-"}
          {" · "}
          보 {trainedInfo.aux_label || trainedInfo.aux || "-"}
        </p>
      ) : null}

      <div>
        <p className="text-sm font-medium">알고리즘 선택</p>
        <div className="mt-2 space-y-2">
          {(meta?.algorithms || []).map((a) => {
            const ok = trainedSet.has(a);
            const role = roleHint(a);
            return (
              <label
                key={a}
                className={`flex items-center gap-2 text-sm ${ok ? "" : "opacity-50"}`}
              >
                <input
                  type="checkbox"
                  disabled={!ok}
                  checked={ok && selected.includes(a)}
                  onChange={(e) => {
                    if (!ok) return;
                    setSelected(
                      e.target.checked
                        ? [...selected.filter((x) => trainedSet.has(x)), a]
                        : selected.filter((x) => x !== a),
                    );
                  }}
                />
                <span>{labelOf(a)}</span>
                {role ? (
                  <span className="text-xs text-emerald-700">({role})</span>
                ) : (
                  <span className="text-xs text-muted-foreground">
                    {ok ? "(이 Run 학습됨)" : "(미학습 · 선택 불가)"}
                  </span>
                )}
              </label>
            );
          })}
        </div>
      </div>

      {err ? <p className="text-sm text-red-600">{err}</p> : null}
      <Button
        onClick={run}
        disabled={busy || !hasTrained || !hasInferData}
        onFocus={() => void refetchPrereq()}
      >
        {busy ? <LoadingSpinner /> : null}
        추론 실행
      </Button>

      {missingOpen ? (
        <SimpleModal title="학습 필요" onClose={() => setMissingOpen(false)}>
          <p className="mb-3 text-sm">
            선택한 알고리즘 중 현재 Run에서 학습된 적이 없는 모델이 있습니다. 「학습 실행」에서
            해당 알고리즘을 먼저 학습한 뒤 추론하세요.
          </p>
          <ul className="mb-4 list-disc space-y-1 pl-5 text-sm">
            {missingLabels.map((name) => (
              <li key={name}>{name}</li>
            ))}
          </ul>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setMissingOpen(false)}>
              닫기
            </Button>
            <AppLink
              href="/pipeline/"
              className="inline-flex h-9 items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground"
            >
              학습 실행으로 이동
            </AppLink>
          </div>
        </SimpleModal>
      ) : null}
    </div>
  );
}
