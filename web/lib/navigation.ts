import { cancelAppQueries } from "@/lib/query-client";

/** 진행 중 API 폴링을 끊고 전체 페이지 이동 (연결 점유·Dialog와 무관하게 사이드바 이동) */
export function hardNavigate(href: string) {
  (document.activeElement as HTMLElement | null)?.blur?.();
  cancelAppQueries();
  window.location.href = href;
}

export function isFileProtocol() {
  return typeof window !== "undefined" && window.location.protocol === "file:";
}
