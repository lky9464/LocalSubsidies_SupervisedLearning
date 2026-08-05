"use client";

import {
  Legend,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
} from "recharts";

export type RadarSeries = {
  id?: string;
  name: string;
  role?: string;
  default_visible?: boolean;
  values: Record<string, number | null>;
  raw?: Record<string, number | null>;
};

type AxisScale = { min: number; max: number };

function formatAxisMax(max: number): string {
  if (max >= 100) return max.toFixed(0);
  if (max >= 10) return max.toFixed(1);
  return max.toFixed(3);
}

function metricTickLabel(metric: string, axisScales: Record<string, AxisScale>): string {
  const scale = axisScales[metric];
  if (!scale) return metric;
  return `${metric}\n(max ${formatAxisMax(scale.max)})`;
}

/** 알고리즘별 고정 색 */
const ALGO_COLORS: Record<string, string> = {
  CatBoost: "#0f766e",
  "Stacked Ensemble": "#ca8a04",
  EasyEnsemble: "#db2777",
  "Gradient Boosting": "#2563eb",
  RandomForest: "#ea580c",
  catboost_v1: "#0d9488",
  catboost_v2: "#115e59",
  stacked_ensemble_v1: "#ca8a04",
  easy_ensemble_v1: "#db2777",
  gradient_boosting_v1: "#2563eb",
  random_forest_v1: "#ea580c",
  random_forest_v2: "#c2410c",
};

const FALLBACK = ["#6366f1", "#14b8a6", "#f59e0b", "#8b5cf6", "#06b6d4", "#ec4899"];

function colorFor(id: string, name: string, index: number): string {
  return ALGO_COLORS[id] || ALGO_COLORS[name] || FALLBACK[index % FALLBACK.length];
}

export function ModelRadarChart({
  metrics,
  series,
  axisScales = {},
  visibleIds,
}: {
  metrics: string[];
  series: RadarSeries[];
  axisScales?: Record<string, AxisScale>;
  visibleIds: Set<string>;
}) {
  const active = series.filter((s) => visibleIds.has(s.id || s.name));

  if (!metrics.length || !series.length) {
    return (
      <p className="text-sm text-muted-foreground">
        모델별 지표비교를 표시할 지표·데이터가 부족합니다.
      </p>
    );
  }

  if (!active.length) {
    return (
      <p className="text-sm text-muted-foreground">
        표시할 모델을 1개 이상 선택하세요.
      </p>
    );
  }

  const data = metrics.map((m) => {
    const row: Record<string, string | number> = { metric: m };
    active.forEach((s, i) => {
      const key = s.id || `series_${i}`;
      row[key] = s.values[m] ?? 0;
    });
    return row;
  });

  return (
    <div className="h-[420px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data}>
          <PolarGrid />
          <PolarAngleAxis
            dataKey="metric"
            tick={{ fontSize: 10 }}
            tickFormatter={(value: string) => metricTickLabel(value, axisScales)}
          />
          <PolarRadiusAxis domain={[0, 1]} tickCount={5} tick={{ fontSize: 10 }} />
          {active.map((s, i) => {
            const key = s.id || `series_${i}`;
            const color = colorFor(key, s.name, i);
            return (
              <Radar
                key={key}
                name={s.name}
                dataKey={key}
                stroke={color}
                fill={color}
                fillOpacity={0.15}
              />
            );
          })}
          <Legend />
        </RadarChart>
      </ResponsiveContainer>
      <p className="mt-2 text-xs text-muted-foreground">
        반경은 선택 지표별 min-max 정규화(0~1)입니다. 축 라벨 max는 해당 Run 비교 모델
        중 최댓값입니다.
      </p>
    </div>
  );
}

export function defaultVisibleSeriesIds(series: RadarSeries[]): Set<string> {
  const ids = new Set<string>();
  for (const s of series) {
    const id = s.id || s.name;
    if (s.default_visible !== false) {
      ids.add(id);
    }
  }
  if (!ids.size) {
    for (const s of series) {
      ids.add(s.id || s.name);
    }
  }
  return ids;
}

export { colorFor as radarColorFor };
