import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * 화면 표시용 — 소수점은 4째 자리에서 반올림해 3째 자리까지.
 * 정수·비수치는 그대로. (원본/DB 값은 변경하지 않음)
 */
export function formatDisplayValue(val: unknown): string {
  if (val == null) return "";
  if (typeof val === "boolean") return val ? "true" : "false";
  if (typeof val === "number") {
    if (!Number.isFinite(val)) return String(val);
    if (Number.isInteger(val)) return String(val);
    return (Math.round(val * 1000) / 1000).toFixed(3);
  }
  if (typeof val === "string") {
    const trimmed = val.trim();
    if (!trimmed) return "";
    if (/^[+-]?\d+$/.test(trimmed)) return trimmed;
    if (/^[+-]?(?:\d+\.\d*|\.\d+)(?:[eE][+-]?\d+)?$/.test(trimmed)) {
      const n = Number(trimmed);
      if (!Number.isFinite(n)) return val;
      if (Number.isInteger(n)) return String(n);
      return (Math.round(n * 1000) / 1000).toFixed(3);
    }
    return val;
  }
  return String(val);
}
