"""System / PC specs."""

from __future__ import annotations

import platform

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/system", tags=["system"])


def _level(value: float, *, high: float, mid: float) -> str:
    if value >= high:
        return "쾌적"
    if value >= mid:
        return "보통"
    return "부족"


@router.get("/pc")
def pc_specs() -> dict:
    try:
        import psutil
    except ImportError as exc:
        raise HTTPException(500, "psutil 미설치") from exc

    mem = psutil.virtual_memory()
    ram_gb = mem.total / (1024**3)
    cpu_logical = psutil.cpu_count(logical=True) or 0
    cpu_phys = psutil.cpu_count(logical=False) or 0
    try:
        disk = psutil.disk_usage("C:\\")
    except Exception:  # noqa: BLE001
        disk = psutil.disk_usage("/")
    free_gb = disk.free / (1024**3)

    ram_lv = _level(ram_gb, high=32, mid=16)
    cpu_lv = _level(float(cpu_logical), high=8, mid=4)
    disk_lv = _level(free_gb, high=50, mid=20)

    rows = [
        {
            "항목명": "OS",
            "내 PC사양": platform.platform(),
            "권장사양": "Windows 10/11 64bit",
            "판정": "-",
        },
        {
            "항목명": "프로세서",
            "내 PC사양": platform.processor() or "(정보 없음)",
            "권장사양": "최근 세대 CPU",
            "판정": "-",
        },
        {
            "항목명": "RAM",
            "내 PC사양": f"{ram_gb:.1f} GB",
            "권장사양": "쾌적 ≥32GB / 보통 16~32GB / 부족 <16GB",
            "판정": ram_lv,
        },
        {
            "항목명": "CPU 논리코어",
            "내 PC사양": f"{cpu_logical} (물리 {cpu_phys})",
            "권장사양": "쾌적 ≥8 / 보통 4~7 / 부족 <4",
            "판정": cpu_lv,
        },
        {
            "항목명": "디스크 여유",
            "내 PC사양": f"{free_gb:.0f} GB",
            "권장사양": "쾌적 ≥50GB / 보통 20~50GB / 부족 <20GB",
            "판정": disk_lv,
        },
    ]

    if ram_lv == "부족" or cpu_lv == "부족":
        guidance = {
            "level": "error",
            "message": (
                "사양이 부족하면 05 학습·Stacked/EasyEnsemble에서 메모리 부족·장시간 소요가 납니다. "
                "알고리즘을 2~3개만 선택하거나 n_jobs를 낮추세요."
            ),
        }
    elif ram_lv == "보통" or cpu_lv == "보통":
        guidance = {
            "level": "warning",
            "message": (
                "보통 사양입니다. 일괄 학습은 가능하나 수 시간이 걸릴 수 있습니다. "
                "절전 모드를 끄고 실행하세요."
            ),
        }
    else:
        guidance = {
            "level": "success",
            "message": "쾌적 사양입니다. 5종 일괄 학습·평가를 무리 없이 진행할 수 있습니다.",
        }

    return {"rows": rows, "guidance": guidance}
