"""내 PC 사양 체크."""

from __future__ import annotations

import platform

import pandas as pd
import streamlit as st


def render() -> None:
    st.title("내 PC 사양 체크")
    st.caption("학습(특히 05) 전 권장 사양을 확인합니다. 로컬에서만 측정합니다.")

    try:
        import psutil
    except ImportError:
        st.error("psutil 미설치 — `pip install psutil` 후 다시 열어주세요.")
        return

    mem = psutil.virtual_memory()
    ram_gb = mem.total / (1024**3)
    cpu_logical = psutil.cpu_count(logical=True) or 0
    cpu_phys = psutil.cpu_count(logical=False) or 0
    try:
        disk = psutil.disk_usage("C:\\")
    except Exception:  # noqa: BLE001
        disk = psutil.disk_usage("/")
    free_gb = disk.free / (1024**3)
    os_name = platform.platform()
    cpu_name = platform.processor() or "(정보 없음)"

    ram_lv = _level(ram_gb, high=32, mid=16)
    cpu_lv = _level(float(cpu_logical), high=8, mid=4)
    disk_lv = _level(free_gb, high=50, mid=20)

    table = pd.DataFrame(
        [
            {
                "항목명": "OS",
                "내 PC사양": os_name,
                "권장사양": "Windows 10/11 64bit",
                "판정": "-",
            },
            {
                "항목명": "프로세서",
                "내 PC사양": cpu_name,
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
    )
    st.dataframe(table, use_container_width=True, hide_index=True)

    st.subheader("영향 안내")
    if ram_lv == "부족" or cpu_lv == "부족":
        st.error(
            "사양이 부족하면 05 학습·Stacked/EasyEnsemble에서 메모리 부족·장시간 소요가 납니다. "
            "알고리즘을 2~3개만 선택하거나 n_jobs를 낮추세요."
        )
    elif ram_lv == "보통" or cpu_lv == "보통":
        st.warning(
            "보통 사양입니다. 일괄 학습은 가능하나 수 시간이 걸릴 수 있습니다. "
            "절전 모드를 끄고 실행하세요."
        )
    else:
        st.success("쾌적 사양입니다. 5종 일괄 학습·평가를 무리 없이 진행할 수 있습니다.")


def _level(value: float, *, high: float, mid: float) -> str:
    if value >= high:
        return "쾌적"
    if value >= mid:
        return "보통"
    return "부족"
