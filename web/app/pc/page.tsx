"use client";

import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import { Alert } from "@/components/ui/alert";
import { DataTable } from "@/components/matrix-table";
import { Skeleton } from "@/components/ui/skeleton";

export default function PcPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["pc"],
    queryFn: () => apiGet<{ rows: Record<string, unknown>[]; guidance: { level: string; message: string } }>("/api/system/pc"),
  });

  if (isLoading) return <Skeleton className="h-48" />;

  const g = data?.guidance;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">내 PC 사양 체크</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          학습(특히 05) 전 권장 사양 · 로컬 측정
        </p>
      </div>

      <DataTable rows={data?.rows || []} />

      <section>
        <h2 className="mb-2 font-medium">영향 안내</h2>
        {g?.level === "error" && <Alert variant="destructive">{g.message}</Alert>}
        {g?.level === "warning" && <Alert>{g.message}</Alert>}
        {g?.level === "success" && <Alert variant="success">{g.message}</Alert>}
      </section>
    </div>
  );
}
