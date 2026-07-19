import type { Metadata } from "next";
import { Providers } from "@/components/providers";
import { AppShell } from "@/components/app-shell";
import { JobBanner } from "@/components/job-banner";
import { FileProtocolGuard } from "@/components/file-protocol-guard";
import "./globals.css";

export const metadata: Metadata = {
  title: "지방보조금 부정수급 위험도 측정",
  description: "로컬 ML 운영 콘솔",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" suppressHydrationWarning>
      <body>
        <Providers>
          <AppShell>
            <FileProtocolGuard />
            <JobBanner />
            {children}
          </AppShell>
        </Providers>
      </body>
    </html>
  );
}
