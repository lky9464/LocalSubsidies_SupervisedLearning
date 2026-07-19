"use client";

import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost, apiPut } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { Alert } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function SettingsPage() {
  const qc = useQueryClient();
  const [dataRoot, setDataRoot] = useState("");
  const [msg, setMsg] = useState("");

  const { data } = useQuery({
    queryKey: ["settings"],
    queryFn: () => apiGet<Record<string, unknown>>("/api/settings"),
  });

  useEffect(() => {
    if (data?.data_root && !dataRoot) {
      setDataRoot(String(data.data_root));
    }
  }, [data, dataRoot]);

  async function saveRoot() {
    const res = await apiPut<{ message: string }>("/api/settings/data-root", {
      data_root: dataRoot,
    });
    setMsg(res.message);
    qc.invalidateQueries({ queryKey: ["settings"] });
  }

  async function initDb() {
    const res = await apiPost<{ message: string }>("/api/settings/db-init");
    setMsg(res.message);
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">설정</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          경로·기본 분할은 여기와 YAML에서 관리합니다.
        </p>
      </div>

      {msg && <Alert variant="success">{msg}</Alert>}

      <Card>
        <CardHeader>
          <CardTitle>경로</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <pre className="rounded-md bg-muted p-3 text-xs">
            data_root = {String(data?.data_root || "(미설정)")}
            {"\n"}ops.sqlite = {String(data?.ops_db_basename || "ops.sqlite")}
          </pre>
          <p className="text-xs text-muted-foreground">
            편집 파일: {String(data?.local_yaml_rel)}
          </p>
          <div>
            <Label htmlFor="dr">data_root 경로</Label>
            <Input id="dr" value={dataRoot} onChange={(e) => setDataRoot(e.target.value)} />
          </div>
          <Button onClick={saveRoot}>local.yaml에 data_root 저장</Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>분할 기본값 (default.yaml)</CardTitle>
        </CardHeader>
        <CardContent>
          <pre className="overflow-auto rounded-md bg-muted p-3 text-xs">
            {JSON.stringify(data?.split_defaults, null, 2)}
          </pre>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>알고리즘</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm">{(data?.algorithms as string[])?.join(", ")}</p>
        </CardContent>
      </Card>

      <Button variant="outline" onClick={initDb}>
        운영 DB 초기화/확인
      </Button>
    </div>
  );
}
