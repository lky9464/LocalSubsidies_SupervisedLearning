"use client";

import { QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { RunProvider } from "@/components/run-context";
import { appQueryClient } from "@/lib/query-client";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider attribute="class" defaultTheme="light" enableSystem={false}>
      <QueryClientProvider client={appQueryClient}>
        <RunProvider>{children}</RunProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
