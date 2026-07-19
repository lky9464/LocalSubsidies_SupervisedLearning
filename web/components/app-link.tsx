"use client";

import { hardNavigate } from "@/lib/navigation";

type AppLinkProps = React.ComponentProps<"a"> & { href: string };

/** Next 클라이언트 라우터 대신 서버/정적 HTML 전체 로드 */
export function AppLink({ href, onClick, ...props }: AppLinkProps) {
  return (
    <a
      href={href}
      {...props}
      onClick={(e) => {
        onClick?.(e);
        if (e.defaultPrevented) return;
        e.preventDefault();
        hardNavigate(href);
      }}
    />
  );
}
