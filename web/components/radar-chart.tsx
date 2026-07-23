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

type Series = { id?: string; name: string; values: Record<string, number | null> };

/** 알고리즘별 고정 색 — family·버전별 구분 */
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
  catboost: "#0f766e",
  stacked_ensemble: "#ca8a04",
  easy_ensemble: "#db2777",
  gradient_boosting: "#2563eb",
  random_forest: "#ea580c",
};

const FALLBACK = ["#6366f1", "#14b8a6", "#f59e0b", "#8b5cf6", "#06b6d4", "#ec4899"];

function colorFor(id: string, name: string, index: number): string {
  return ALGO_COLORS[id] || ALGO_COLORS[name] || FALLBACK[index % FALLBACK.length];
}

export function ModelRadarChart({
  metrics,
  series,
}: {
  metrics: string[];
  series: Series[];
}) {
  if (!metrics.length || !series.length) {
    return (
      <p className="text-sm text-muted-foreground">
        모델별 지표비교를 표시할 지표·데이터가 부족합니다.
      </p>
    );
  }

  const data = metrics.map((m) => {
    const row: Record<string, string | number> = { metric: m };
    series.forEach((s, i) => {
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
          <PolarAngleAxis dataKey="metric" tick={{ fontSize: 11 }} />
          <PolarRadiusAxis domain={[0, 1]} tick={false} />
          {series.map((s, i) => {
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
    </div>
  );
}
