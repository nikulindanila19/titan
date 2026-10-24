# -*- coding: utf-8 -*-
"""
upk_timing_checker.py — Проверка процессуальных сроков по УПК РФ.
"""
from datetime import date, timedelta
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class TimingResult:
    rule_id: str
    rule_name: str
    status: str          # "ok" | "warning" | "error" | "info" | "skipped"
    message: str
    source: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


# ==========================================
# НОРМЫ УПК РФ (в днях / месяцах)
# ==========================================
# Ст. 100 УПК РФ: срок задержания до предъявления обвинения — 10 суток (для отдельных составов — 30).
# Ст. 108 УПК РФ: срок содержания под стражей на предварительном следствии — 2 месяца.
# Ст. 109 УПК РФ: продление до 6, 12, 18 месяцев.
# Ст. 162 УПК РФ: срок предварительного следствия — 2 месяца (продление до 3, 12).
# Ст. 223 УПК РФ: срок дознания — 30 суток (продление до 60, 90, 12 месяцев).

UPK_RULES = {
    "art100": {"name": "Ст. 100 УПК РФ — срок задержания до обвинения", "days": 10},
    "art108": {"name": "Ст. 108 УПК РФ — срок содержания под стражей", "months": 2},
    "art162": {"name": "Ст. 162 УПК РФ — срок предварительного следствия", "months": 2},
    "art223": {"name": "Ст. 223 УПК РФ — срок дознания", "days": 30},
}


def _months_between(d1, d2):
    """Приблизительное число месяцев между датами."""
    if not d1 or not d2:
        return None
    days = (d2 - d1).days
    return days / 30.44  # среднее число дней в месяце


def _days_between(d1, d2):
    if not d1 or not d2:
        return None
    return (d2 - d1).days


# ==========================================
# ПРАВИЛО 1: Ст. 100 УПК РФ — задержание до обвинения
# ==========================================
def check_art100(dates):
    d_det = dates.get("date_detention")
    d_charge = dates.get("date_charge")
    if not d_det or not d_charge:
        return TimingResult("art100", UPK_RULES["art100"]["name"], "skipped",
                            "Нет данных о дате задержания или предъявления обвинения.")

    days = _days_between(d_det, d_charge)
    if days is None:
        return TimingResult("art100", UPK_RULES["art100"]["name"], "skipped", "Не удалось вычислить срок.")

    limit = UPK_RULES["art100"]["days"]
    if days > limit:
        return TimingResult("art100", UPK_RULES["art100"]["name"], "error",
                            f"С момента задержания до предъявления обвинения прошло {days} дней, "
                            f"а по ст. 100 УПК РФ — не более {limit} суток.",
                            source="Ст. 100 УПК РФ",
                            details={"days": days, "limit": limit})
    return TimingResult("art100", UPK_RULES["art100"]["name"], "ok",
                        f"Срок от задержания до обвинения — {days} дней (норма — до {limit}).")


# ==========================================
# ПРАВИЛО 2: Ст. 108 УПК РФ — срок содержания под стражей
# ==========================================
def check_art108(dates):
    d_mera = dates.get("date_mera_pres")
    d_final = dates.get("date_final")
    if not d_mera or not d_final:
        return TimingResult("art108", UPK_RULES["art108"]["name"], "skipped",
                            "Нет данных о дате избрания меры пресечения или окончания следствия.")

    months = _months_between(d_mera, d_final)
    if months is None:
        return TimingResult("art108", UPK_RULES["art108"]["name"], "skipped", "Не удалось вычислить срок.")

    limit = UPK_RULES["art108"]["months"]
    if months > limit:
        return TimingResult("art108", UPK_RULES["art108"]["name"], "warning",
                            f"Содержание под стражей длится примерно {months:.1f} мес., "
                            f"что превышает базовый срок по ст. 108 УПК РФ ({limit} мес.). "
                            f"Требуется проверка постановления о продлении (ст. 109 УПК РФ).",
                            source="Ст. 108, 109 УПК РФ",
                            details={"months": months, "limit": limit})
    return TimingResult("art108", UPK_RULES["art108"]["name"], "ok",
                        f"Срок содержания под стражей — {months:.1f} мес. (базовый предел — {limit}).")


# ==========================================
# ПРАВИЛО 3: Ст. 162 УПК РФ — срок предварительного следствия
# ==========================================
def check_art162(dates):
    d_crime = dates.get("date_crime") or dates.get("date_document")
    d_final = dates.get("date_final")
    if not d_crime or not d_final:
        return TimingResult("art162", UPK_RULES["art162"]["name"], "skipped",
                            "Нет данных о дате преступления (или документа) и окончания следствия.")

    months = _months_between(d_crime, d_final)
    if months is None:
        return TimingResult("art162", UPK_RULES["art162"]["name"], "skipped", "Не удалось вычислить срок.")

    limit = UPK_RULES["art162"]["months"]
    if months > limit:
        return TimingResult("art162", UPK_RULES["art162"]["name"], "warning",
                            f"С момента преступления до окончания следствия прошло примерно {months:.1f} мес. "
                            f"(базовый срок по ст. 162 УПК РФ — {limit} мес.). "
                            f"Проверьте постановления о продлении.",
                            source="Ст. 162 УПК РФ",
                            details={"months": months, "limit": limit})
    return TimingResult("art162", UPK_RULES["art162"]["name"], "ok",
                        f"Срок следствия — {months:.1f} мес. (базовый предел — {limit}).")


# ==========================================
# ПРАВИЛО 4: Ст. 223 УПК РФ — срок дознания
# ==========================================
def check_art223(dates, doc_type):
    if doc_type != "постановление_о_возбуждении":
        return TimingResult("art223", UPK_RULES["art223"]["name"], "skipped",
                            "Документ не является постановлением о возбуждении уголовного дела.")

    d_doc = dates.get("date_document")
    d_final = dates.get("date_final")
    if not d_doc or not d_final:
        return TimingResult("art223", UPK_RULES["art223"]["name"], "skipped",
                            "Нет данных о дате возбуждения или окончания дознания.")

    days = _days_between(d_doc, d_final)
    if days is None:
        return TimingResult("art223", UPK_RULES["art223"]["name"], "skipped", "Не удалось вычислить срок.")

    limit = UPK_RULES["art223"]["days"]
    if days > limit:
        return TimingResult("art223", UPK_RULES["art223"]["name"], "warning",
                            f"С момента возбуждения дела прошло {days} дней, "
                            f"а срок дознания по ст. 223 УПК РФ — {limit} суток. Требуется проверка продления.",
                            source="Ст. 223 УПК РФ",
                            details={"days": days, "limit": limit})
    return TimingResult("art223", UPK_RULES["art223"]["name"], "ok",
                        f"Срок дознания — {days} дней (норма — до {limit}).")


# ==========================================
# ГЛАВНАЯ ФУНКЦИЯ
# ==========================================
def check_timing(dates, doc_type):
    """Проверяет все применимые процессуальные сроки."""
    results = []
    results.append(check_art100(dates))
    results.append(check_art108(dates))
    results.append(check_art162(dates))
    results.append(check_art223(dates, doc_type))
    return results


def format_timing_block(results):
    """Форматирует результаты проверки сроков в текстовый блок."""
    if not results:
        return ""
    lines = [
        "",
        "=" * 60,
        "⏱️ ПРОВЕРКА ПРОЦЕССУАЛЬНЫХ СРОКОВ ПО УПК РФ",
        "=" * 60,
    ]
    icons = {"ok": "✅", "warning": "⚠️", "error": "❌", "info": "ℹ️", "skipped": "➖"}
    for r in results:
        icon = icons.get(r.status, "•")
        lines.append(f"{icon} {r.rule_name}: {r.message}")
        if r.source:
            lines.append(f"    → {r.source}")
    return "\n".join(lines)