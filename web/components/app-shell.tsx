"use client";

import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import {
  Activity,
  BookOpen,
  ChevronDown,
  ChevronRight,
  Database,
  History,
  LayoutDashboard,
  Monitor,
  Moon,
  Settings,
  Sun,
  Tag,
  Workflow,
} from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { hardNavigate } from "@/lib/navigation";
import { useRun } from "@/components/run-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const nav = [
  { href: "/", label: "대시보드", icon: LayoutDashboard },
  { href: "/run-issue/", label: "Run ID 발급", icon: Activity },
  { href: "/data/", label: "데이터 등록", icon: Database },
];

const trainNav = [
  { href: "/pipeline/", label: "학습 실행" },
  { href: "/models/", label: "모델 비교·평가" },
  { href: "/ops/", label: "타겟 포착 분포" },
];

const inferNav = [
  { href: "/inference/run/", label: "추론 실행" },
  { href: "/inference/results/", label: "결과 확인" },
];

const bottomNav = [
  { href: "/history/", label: "Run 이력", icon: History },
  { href: "/pc/", label: "내 PC 사양 체크", icon: Monitor },
  { href: "/guide/", label: "사용자 가이드", icon: BookOpen },
  { href: "/settings/", label: "설정", icon: Settings },
];

function NavLink({
  href,
  label,
  icon: Icon,
  indent,
}: {
  href: string;
  label: string;
  icon?: React.ComponentType<{ className?: string }>;
  indent?: boolean;
}) {
  const pathname = usePathname();
  const active = pathname === href || pathname === href.replace(/\/$/, "");
  return (
    <a
      href={href}
      className={cn(
        "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
        indent && "pl-8",
        active ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground",
      )}
      onClick={(e) => {
        e.preventDefault();
        hardNavigate(href);
      }}
    >
      {Icon && <Icon className="h-4 w-4 shrink-0" />}
      {label}
    </a>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { theme, setTheme } = useTheme();
  const { runId, setRunId, runs, loading } = useRun();
  const pathname = usePathname();
  const [trainOpen, setTrainOpen] = useState(
    trainNav.some((n) => pathname.startsWith(n.href.replace(/\/$/, ""))),
  );
  const [inferOpen, setInferOpen] = useState(pathname.startsWith("/inference"));

  return (
    <div className="flex min-h-screen bg-background">
      <aside className="flex w-64 shrink-0 flex-col border-r border-border bg-card/30">
        <div className="border-b border-border p-4">
          <p className="text-sm font-semibold leading-snug">
            지방보조금
            <br />
            부정수급 위험도 측정
          </p>
          <p className="mt-2 text-xs text-muted-foreground">bind: 127.0.0.1 · raw∉DB</p>
        </div>
        <nav className="flex-1 space-y-1 overflow-y-auto p-3">
          {nav.map((item) => (
            <NavLink key={item.href} {...item} />
          ))}
          <div className="my-2 border-t border-border" />
          <button
            type="button"
            className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-muted"
            onClick={() => setTrainOpen(!trainOpen)}
          >
            {trainOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            <Workflow className="h-4 w-4" />
            모델 학습 및 평가
          </button>
          {trainOpen &&
            trainNav.map((item) => (
              <NavLink key={item.href} href={item.href} label={item.label} indent />
            ))}
          <div className="my-2 border-t border-border" />
          <button
            type="button"
            className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-muted"
            onClick={() => setInferOpen(!inferOpen)}
          >
            {inferOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            추론
          </button>
          {inferOpen &&
            inferNav.map((item) => (
              <NavLink key={item.href} href={item.href} label={item.label} indent />
            ))}
          <div className="my-2 border-t border-border" />
          {bottomNav.map((item) => (
            <NavLink key={item.href} {...item} />
          ))}
          <div className="my-2 border-t border-border" />
          <NavLink href="/version/" label="버전 정보" icon={Tag} />
          <div className="my-2 border-t border-border" />
        </nav>
      </aside>      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-6 py-3">
          <div className="flex min-w-0 flex-1 flex-wrap items-center gap-3">
            <span className="shrink-0 text-sm text-muted-foreground">현재 Run</span>
            <Select
              value={runId || undefined}
              onValueChange={(v) => setRunId(v)}
              disabled={loading || runs.length === 0}
            >
              <SelectTrigger className="w-[220px] shrink-0">
                <SelectValue placeholder="Run 선택" />
              </SelectTrigger>
              <SelectContent>
                {runs.map((r) => (
                  <SelectItem key={r.run_id} value={r.run_id}>
                    {r.run_id}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input
              readOnly
              tabIndex={-1}
              aria-label="작업내용"
              title={
                runs.find((r) => r.run_id === runId)?.work_content?.trim() ||
                "작업내용 없음"
              }
              value={
                runs.find((r) => r.run_id === runId)?.work_content?.trim() ||
                (runId ? "(작업내용 없음)" : "")
              }
              placeholder="작업내용"
              className="min-w-[20rem] flex-1 cursor-default bg-muted/40 text-muted-foreground focus-visible:ring-0"
              onFocus={(e) => e.currentTarget.blur()}
            />
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="shrink-0"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            aria-label="테마 전환"
          >
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>
        </header>
        <main className="flex-1 overflow-auto p-6">{children}</main>
      </div>
    </div>
  );
}
