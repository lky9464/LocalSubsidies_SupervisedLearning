"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  FeatureDistributionChartBody,
  type FeatureDistributionPayload,
} from "@/components/feature-distribution-chart";
import type { ShapBarRow } from "@/components/shap-bar-chart";

type Props = {
  runId: string;
  roleKey: string;
  roleTitle: string;
  modelLabel?: string | null;
  top10: ShapBarRow[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

export function FeatureDistributionDialog({
  runId,
  roleKey,
  roleTitle,
  modelLabel,
  top10,
  open,
  onOpenChange,
}: Props) {
  const [rank, setRank] = useState(1);
  const [unit, setUnit] = useState<"pk" | "entity">("pk");

  useEffect(() => {
    if (open) {
      setRank(1);
      setUnit("pk");
    }
  }, [open, roleKey]);

  const { data, isLoading } = useQuery({
    queryKey: ["feature-distribution", runId, roleKey, rank, unit],
    queryFn: () =>
      apiGet<FeatureDistributionPayload>(
        `/api/runs/${runId}/models/feature-distribution?role=${roleKey}&rank=${rank}&unit=${unit}`,
      ),
    enabled: open && !!runId,
  });

  const featLabel = data?.feature_ko || data?.feature || top10[rank - 1]?.feature_ko;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {roleTitle} · TOP10별 점수분포
            {modelLabel ? (
              <span className="ml-1 text-sm font-normal text-muted-foreground">
                ({modelLabel})
              </span>
            ) : null}
          </DialogTitle>
        </DialogHeader>

        <Tabs value={unit} onValueChange={(v) => setUnit(v as "pk" | "entity")}>
          <TabsList>
            <TabsTrigger value="pk">PK기준</TabsTrigger>
            <TabsTrigger value="entity">엔티티기준</TabsTrigger>
          </TabsList>
          <TabsContent value={unit} className="space-y-4">
            <div className="flex flex-wrap gap-1">
              {(top10.length ? top10 : Array.from({ length: 10 }, (_, i) => ({ rank: i + 1 }))).map(
                (_, i) => {
                  const r = i + 1;
                  const label = top10[i]?.feature_ko || top10[i]?.feature || `TOP${r}`;
                  return (
                    <Button
                      key={r}
                      type="button"
                      size="sm"
                      variant={rank === r ? "default" : "outline"}
                      className="text-xs"
                      onClick={() => setRank(r)}
                    >
                      {r}. {label.length > 12 ? `${label.slice(0, 12)}…` : label}
                    </Button>
                  );
                },
              )}
            </div>

            <p className="text-sm text-muted-foreground">
              {featLabel}
              {data?.kind === "numeric" ? " · 수치형" : data?.kind === "categorical" ? " · 범주형" : ""}
            </p>

            {isLoading ? (
              <p className="text-sm text-muted-foreground">불러오는 중…</p>
            ) : (
              <FeatureDistributionChartBody payload={data || { available: false }} />
            )}
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
