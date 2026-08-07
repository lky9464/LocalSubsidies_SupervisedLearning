"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";

type NumericPayload = {
  scatter: { x: number; y: number }[];
  binned: { x: number; y_mean: number; n: number }[];
  regression: {
    slope: number | null;
    intercept: number | null;
    points: { x: number; y: number }[];
  };
};

type CategoricalPayload = {
  bars: { category: string; mean_score: number; count: number }[];
  other: {
    category_count: number;
    total_count: number;
    mean_score: number;
  } | null;
};

export function NumericFeatureChart({ data }: { data: NumericPayload }) {
  const scatter = data.scatter.map((p) => ({ x: p.x, y: p.y, kind: "scatter" }));
  const binned = data.binned.map((p) => ({ x: p.x, y: p.y_mean, kind: "binned" }));
  const regression = (data.regression.points || []).map((p) => ({
    x: p.x,
    y: p.y,
    kind: "regression",
  }));

  if (!scatter.length && !binned.length) {
    return <p className="text-sm text-muted-foreground">표시할 데이터 없음</p>;
  }

  return (
    <div className="h-[360px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            type="number"
            dataKey="x"
            name="피처값"
            tick={{ fontSize: 10 }}
            label={{ value: "피처값", position: "insideBottom", offset: -4, fontSize: 11 }}
          />
          <YAxis
            type="number"
            dataKey="y"
            name="위험도점수"
            tick={{ fontSize: 10 }}
            domain={[0, 1000]}
            label={{ value: "위험도점수", angle: -90, position: "insideLeft", fontSize: 11 }}
          />
          <ZAxis range={[20, 20]} />
          <Tooltip
            cursor={{ strokeDasharray: "3 3" }}
            formatter={(v: number, name: string) => {
              if (name === "표본") return [v, "위험도점수"];
              if (name === "구간 평균") return [v, "평균 점수"];
              if (name === "회귀직선") return [v, "예측 점수"];
              return [v, name];
            }}
          />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Scatter name="표본" data={scatter} fill="#93c5fd" fillOpacity={0.35} />
          <Line
            name="구간 평균"
            data={binned}
            type="monotone"
            dataKey="y"
            stroke="#2563eb"
            strokeWidth={2.5}
            dot={{ r: 4, fill: "#2563eb" }}
            legendType="line"
            connectNulls
          />
          <Line
            name="회귀직선"
            data={regression}
            type="linear"
            dataKey="y"
            stroke="#dc2626"
            strokeWidth={2}
            strokeDasharray="8 4"
            dot={false}
            legendType="line"
            connectNulls
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

export function CategoricalFeatureChart({ data }: { data: CategoricalPayload }) {
  const bars = [...data.bars].sort((a, b) => b.mean_score - a.mean_score);
  if (data.other) {
    bars.push({
      category: "기타",
      mean_score: data.other.mean_score,
      count: data.other.total_count,
    });
  }

  if (!bars.length) {
    return <p className="text-sm text-muted-foreground">표시할 데이터 없음</p>;
  }

  return (
    <div className="space-y-2">
      <div className="h-[min(400px,40vh)] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            layout="vertical"
            data={bars}
            margin={{ top: 4, right: 16, left: 8, bottom: 4 }}
          >
            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
            <XAxis type="number" domain={[0, 1000]} tick={{ fontSize: 10 }} />
            <YAxis
              type="category"
              dataKey="category"
              width={100}
              tick={{ fontSize: 9 }}
            />
            <Tooltip
              formatter={(v: number, name: string) => {
                if (name === "mean_score") return [v, "평균 위험도점수"];
                return [v, name];
              }}
              labelFormatter={(l) => String(l)}
            />
            <Bar dataKey="mean_score" fill="#6366f1" radius={[0, 2, 2, 0]} name="mean_score" />
          </BarChart>
        </ResponsiveContainer>
      </div>
      {data.other ? (
        <p className="text-xs text-muted-foreground">
          「기타」: 상위 10개를 제외한 {data.other.category_count}개 범주 ·{" "}
          {data.other.total_count.toLocaleString()}건 · 평균 점수 {data.other.mean_score}
        </p>
      ) : null}
      <p className="text-[10px] text-muted-foreground">위험도점수 높은 범주가 위쪽</p>
    </div>
  );
}

export type FeatureDistributionPayload = {
  available?: boolean;
  reason?: string;
  kind?: "numeric" | "categorical";
  feature?: string;
  feature_ko?: string;
  numeric?: NumericPayload;
  categorical?: CategoricalPayload;
};

export function FeatureDistributionChartBody({ payload }: { payload: FeatureDistributionPayload }) {
  if (!payload.available) {
    return <p className="text-sm text-muted-foreground">{payload.reason || "데이터 없음"}</p>;
  }
  if (payload.kind === "numeric" && payload.numeric) {
    return <NumericFeatureChart data={payload.numeric} />;
  }
  if (payload.kind === "categorical" && payload.categorical) {
    return <CategoricalFeatureChart data={payload.categorical} />;
  }
  return <p className="text-sm text-muted-foreground">차트 데이터 없음</p>;
}
