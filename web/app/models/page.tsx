"use client";

import { AppLink } from "@/components/app-link";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import { useRun } from "@/components/run-context";
import { Alert } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DataTable } from "@/components/matrix-table";
import {
  ModelRadarChart,
  defaultVisibleSeriesIds,
  type RadarSeries,
  radarColorFor,
} from "@/components/radar-chart";
import { PrCurveChart, type PrCurvePayload } from "@/components/pr-curve-chart";
import { ShapImportanceBarChart, type ShapBarRow } from "@/components/shap-bar-chart";
import {
  ScoreDistributionBarChart,
  type ScoreBinRow,
} from "@/components/score-distribution-chart";
import { FeatureDistributionDialog } from "@/components/feature-distribution-dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Checkbox } from "@/components/ui/checkbox";

const DEFAULT_RADAR_METRICS = [
  "PR-AUC",
  "상위1%리프트",
  "상위1%양성비중",
  "상위1%양성포착",
];

type RolePanel<T> = {
  role: string;
  algo?: string | null;
  label?: string | null;
  available: boolean;
  reason?: string;
} & T;

type ShapPanel = RolePanel<{ top10: ShapBarRow[] }>;
type PrPanel = RolePanel<{ curve: PrCurvePayload | null }>;
type ScoreDistPanel = RolePanel<{
  pk?: { bins: ScoreBinRow[]; total?: number };
  entity?: { bins: ScoreBinRow[]; total?: number };
}>;

type FeatureDialogState = {
  roleKey: string;
  roleTitle: string;
  label: string | null;
  top10: ShapBarRow[];
} | null;

const ROLE_ORDER = [
  { key: "primary", title: "주 모델" },
  { key: "aux", title: "보조 모델" },
  { key: "reference", title: "참조 모델" },
] as const;

function RoleTriplePanel({
  panels,
  renderAvailable,
  renderEmpty,
}: {
  panels: Record<string, RolePanel<unknown>>;
  renderAvailable: (key: string, panel: RolePanel<unknown>) => ReactNode;
  renderEmpty: (key: string, panel: RolePanel<unknown>) => ReactNode;
}) {
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      {ROLE_ORDER.map(({ key, title }) => {
        const panel = panels[key];
        if (!panel) return null;
        return (
          <div key={key} className="min-w-0 rounded-lg border p-3">
            <h4 className="mb-2 text-sm font-semibold">
              {title}
              {panel.label ? (
                <span className="ml-1 font-normal text-muted-foreground">({panel.label})</span>
              ) : null}
            </h4>
            {panel.available ? renderAvailable(key, panel) : renderEmpty(key, panel)}
          </div>
        );
      })}
    </div>
  );
}

export default function ModelsPage() {
  const { runId } = useRun();
  const [metrics, setMetrics] = useState<string[]>(DEFAULT_RADAR_METRICS);
  const [visibleSeries, setVisibleSeries] = useState<Set<string>>(new Set());
  const [scoreUnit, setScoreUnit] = useState<"pk" | "entity">("pk");
  const [featureDialog, setFeatureDialog] = useState<FeatureDialogState>(null);
  const [featureDialogOpen, setFeatureDialogOpen] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["models", runId, metrics.join(",")],
    queryFn: () =>
      apiGet<Record<string, unknown>>(
        `/api/runs/${runId}/models?metrics=${encodeURIComponent(metrics.join(","))}`,
      ),
    enabled: !!runId,
  });

  const { data: scoreDist, isLoading: scoreDistLoading } = useQuery({
    queryKey: ["models", runId, "score-distribution"],
    queryFn: () =>
      apiGet<{ panels: Record<string, ScoreDistPanel> }>(
        `/api/runs/${runId}/models/score-distribution`,
      ),
    enabled: !!runId && !data?.empty,
  });

  const scorePanels = scoreDist?.panels || {};

  const radar = (data?.radar as {
    metrics?: string[];
    series?: RadarSeries[];
    axis_scales?: Record<string, { min: number; max: number }>;
  }) || { metrics: [], series: [], axis_scales: {} };

  const series = radar.series || [];

  useEffect(() => {
    setVisibleSeries(defaultVisibleSeriesIds(series));
  }, [runId, series.map((s) => s.id).join("|")]);

  const available = (data?.radar_metrics_available as string[]) || [];
  const insights = (data?.insights as {
    shap?: Record<string, ShapPanel>;
    pr_curve?: Record<string, PrPanel>;
  }) || { shap: {}, pr_curve: {} };

  const metricHelp = (data?.metric_help as Record<string, string>) || {};

  const toggleSeries = (id: string, checked: boolean) => {
    setVisibleSeries((prev) => {
      const next = new Set(prev);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  };

  const radarLegend = useMemo(
    () =>
      series.map((s, i) => ({
        id: s.id || s.name,
        name: s.name,
        color: radarColorFor(s.id || s.name, s.name, i),
      })),
    [series],
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">모델 비교·평가</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          결과 조회용 — 재실행은{" "}
          <AppLink href="/pipeline/" className="underline">
            학습 실행
          </AppLink>{" "}
          05~10에서. SHAP·PR curve는 선택 Run의 06·07 최신 산출물 기준입니다.
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
                  {Object.entries(metricHelp).map(([k, v]) => (
                    <li key={k}>
                      <strong>{k}</strong>: {v}
                    </li>
                  ))}
                </ul>
              </details>
              <DataTable rows={(data?.ranking as Record<string, unknown>[]) || []} />
              {data?.ranking_confidence === "low" && data?.ranking_note ? (
                <Alert variant="default">{String(data.ranking_note)}</Alert>
              ) : null}
              <p className="text-xs text-muted-foreground">
                순위: 상위1% 리프트(Δ≥3%면 단독) → PR-AUC(근접 시) · 1위=주·2위=보 · 3순위=참
                (docs/ranking_methodology.md)
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>모델별 지표비교</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <p className="mb-2 text-sm font-medium">표시 지표 (3개 이상)</p>
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
              </div>
              {metrics.length < 3 && (
                <Alert>표시할 지표를 3개 이상 선택하세요.</Alert>
              )}

              <div>
                <p className="mb-2 text-sm font-medium">표시 모델</p>
                <div className="flex flex-wrap gap-3">
                  {radarLegend.map((s) => (
                    <label key={s.id} className="flex items-center gap-2 text-sm">
                      <Checkbox
                        checked={visibleSeries.has(s.id)}
                        onCheckedChange={(c) => toggleSeries(s.id, !!c)}
                      />
                      <span
                        className="inline-block h-2.5 w-2.5 rounded-full"
                        style={{ backgroundColor: s.color }}
                      />
                      {s.name}
                    </label>
                  ))}
                </div>
              </div>

              <ModelRadarChart
                metrics={radar.metrics || metrics}
                series={series}
                axisScales={radar.axis_scales || {}}
                visibleIds={visibleSeries}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>점수 분포 (Test)</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <details className="text-sm">
                <summary className="cursor-pointer font-medium">점수 분포 설명</summary>
                <p className="mt-2 text-muted-foreground">
                  위험도점수 100점 단위 10구간(07과 동일: [0,100) … [900,1000])별 분포입니다.
                  막대 높이는 전체 건수, 색 농도는 Target 건수(모델·구간 내 비교, Target 0=흰색)입니다.
                  엔티티 기준은 타겟 포착 분포와 동일하게 PFM_BIZ_ID+INST_ID 평균 점수입니다.
                </p>
              </details>
              {scoreDistLoading ? (
                <Skeleton className="h-48" />
              ) : (
                <Tabs value={scoreUnit} onValueChange={(v) => setScoreUnit(v as "pk" | "entity")}>
                  <TabsList>
                    <TabsTrigger value="pk">PK기준</TabsTrigger>
                    <TabsTrigger value="entity">엔티티기준</TabsTrigger>
                  </TabsList>
                  <TabsContent value={scoreUnit}>
                    <RoleTriplePanel
                      panels={scorePanels as Record<string, RolePanel<unknown>>}
                      renderAvailable={(_key, panel) => {
                        const p = panel as ScoreDistPanel;
                        const block = scoreUnit === "pk" ? p.pk : p.entity;
                        const bins = block?.bins || [];
                        return <ScoreDistributionBarChart bins={bins} />;
                      }}
                      renderEmpty={(_key, panel) => (
                        <p className="text-sm text-muted-foreground">
                          {panel.reason || "해당 없음"}
                        </p>
                      )}
                    />
                  </TabsContent>
                </Tabs>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>변수중요도 (SHAP TOP10)</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <details className="text-sm">
                <summary className="cursor-pointer font-medium">SHAP 차트 설명</summary>
                <p className="mt-2 text-muted-foreground">
                  Test 표본 SHAP 기준 변수별 기여비중(절대 크기, TOP10)입니다. 막대 길이는 중요도
                  크기만 나타내며 점수 상승·하락 방향과는 무관합니다. 점검 우선순위(위험도
                  점수)와 별개의 참고 자료입니다.
                </p>
              </details>
              <div className="grid gap-4 lg:grid-cols-3">
                {ROLE_ORDER.map(({ key, title }) => {
                  const panel = (insights.shap || {})[key] as ShapPanel | undefined;
                  if (!panel) return null;
                  return (
                    <div key={key} className="relative min-w-0 rounded-lg border p-3 pt-10">
                      {panel.available ? (
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          className="absolute right-2 top-2 text-xs"
                          onClick={() => {
                            setFeatureDialog({
                              roleKey: key,
                              roleTitle: title,
                              label: panel.label || null,
                              top10: panel.top10 || [],
                            });
                            setFeatureDialogOpen(true);
                          }}
                        >
                          TOP10별 점수분포
                        </Button>
                      ) : null}
                      <h4 className="mb-2 text-sm font-semibold">
                        {title}
                        {panel.label ? (
                          <span className="ml-1 font-normal text-muted-foreground">
                            ({panel.label})
                          </span>
                        ) : null}
                      </h4>
                      {panel.available ? (
                        <ShapImportanceBarChart rows={panel.top10} />
                      ) : (
                        <p className="text-sm text-muted-foreground">
                          {panel.reason || "해당 없음"}
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>PR-AUC</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <details className="text-sm">
                <summary className="cursor-pointer font-medium">PR-AUC 설명</summary>
                <p className="mt-2 text-muted-foreground">
                  {metricHelp["PR-AUC"] ||
                    "Precision-Recall 곡선 아래 면적. 불균형 데이터에서 양성 구분력을 봅니다."}
                </p>
              </details>
              <RoleTriplePanel
                panels={insights.pr_curve || {}}
                renderAvailable={(_key, panel) => {
                  const p = panel as PrPanel;
                  if (!p.curve) return null;
                  return <PrCurveChart curve={p.curve} label={p.label || ""} />;
                }}
                renderEmpty={(_key, panel) => (
                  <p className="text-sm text-muted-foreground">{panel.reason || "해당 없음"}</p>
                )}
              />
            </CardContent>
          </Card>
        </>
      )}

      {featureDialog && runId ? (
        <FeatureDistributionDialog
          runId={runId}
          roleKey={featureDialog.roleKey}
          roleTitle={featureDialog.roleTitle}
          modelLabel={featureDialog.label}
          top10={featureDialog.top10}
          open={featureDialogOpen}
          onOpenChange={setFeatureDialogOpen}
        />
      ) : null}

      <Alert>
        재실행은 「학습 실행」05~10에서 하세요. Test 4×4는 「타겟 포착 분포」 메뉴에서
        확인합니다.
      </Alert>
    </div>
  );
}
