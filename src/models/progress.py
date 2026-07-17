"""학습 진행률 표시 (tqdm 우선, 없으면 텍스트 폴백)."""

from __future__ import annotations

from typing import Any, Iterable

try:
    from tqdm.auto import tqdm as _tqdm

    _HAS_TQDM = True
except ImportError:  # pragma: no cover
    _HAS_TQDM = False
    _tqdm = None  # type: ignore


class _TextPbar:
    """tqdm 미설치 시 간단한 텍스트 진행 표시."""

    def __init__(self, total: int, desc: str = "") -> None:
        self.total = max(int(total), 1)
        self.desc = desc
        self.n = 0
        self._last_pct = -1
        print(f"[progress] {desc} 시작 (total={self.total})")

    def update(self, n: int = 1) -> None:
        self.n = min(self.n + n, self.total)
        pct = int(100 * self.n / self.total)
        if pct >= self._last_pct + 5 or self.n >= self.total:
            print(f"[progress] {self.desc}: {self.n}/{self.total} ({pct}%)")
            self._last_pct = pct

    def close(self) -> None:
        if self.n < self.total:
            self.update(self.total - self.n)
        print(f"[progress] {self.desc} 완료")

    def set_postfix_str(self, s: str) -> None:
        print(f"[progress] 현재: {s}")


class _TextAlgoIter:
    def __init__(self, items: list[str], desc: str) -> None:
        self.items = items
        self.desc = desc
        self._i = 0

    def __iter__(self):
        total = len(self.items)
        for i, item in enumerate(self.items, start=1):
            print(f"[progress] {self.desc}: {i}/{total} → {item}")
            self._i = i
            yield item

    def set_postfix_str(self, s: str) -> None:
        print(f"[progress] 현재 알고리즘: {s}")


class CatBoostTqdmCallback:
    """CatBoost iteration 진행바."""

    def __init__(self, total_iterations: int, desc: str = "CatBoost") -> None:
        if _HAS_TQDM:
            self.pbar: Any = _tqdm(
                total=total_iterations,
                desc=desc,
                leave=False,
                unit="iter",
                dynamic_ncols=True,
            )
        else:
            self.pbar = _TextPbar(total_iterations, desc=desc)
        self._last = 0

    def after_iteration(self, info: Any) -> bool:
        cur = int(getattr(info, "iteration", 0)) + 1
        delta = max(0, cur - self._last)
        if delta:
            self.pbar.update(delta)
            self._last = cur
        return True

    def close(self) -> None:
        total = getattr(self.pbar, "total", None)
        n = getattr(self.pbar, "n", 0)
        if total is not None and n < total:
            self.pbar.update(total - n)
        self.pbar.close()


def algo_progress(algorithms: list[str], desc: str = "알고리즘") -> Iterable[str]:
    """알고리즘 전환용 진행바."""
    if _HAS_TQDM:
        return _tqdm(algorithms, desc=desc, unit="model", dynamic_ncols=True)
    return _TextAlgoIter(list(algorithms), desc)


def progress_backend_name() -> str:
    return "tqdm" if _HAS_TQDM else "text_fallback"
