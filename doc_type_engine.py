# -*- coding: utf-8 -*-
"""
doc_type_engine.py — Определение типа процессуального документа
и извлечение ключевых дат для проверки сроков по УПК РФ.
Устойчиво к OCR-ошибкам (пробелы между буквами, переносы строк).
"""
import re
from datetime import datetime, date


DOC_TYPE_MARKERS = {
    "приговор": ["приговор", "именемроссийскойфедерации", "приговорил"],
    "обвинительное_заключение": ["обвинительноезаключение", "обвиняемый", "обвиняетсявсовершении"],
    "постановление_о_возбуждении": ["постановлениеовозбужденииуголовногодела", "возбудитьуголовноедело"],
    "постановление_о_привлечении": ["постановлениеопривлечениивкачествеобвиняемого", "привлечьвкачествеобвиняемого"],
    "постановление_о_мере_пресечения": ["постановлениеобизбраниимерыпресечения", "заключениеподстражу", "домашнийарест", "подпискаоnotвыезде"],
    "протокол_задержания": ["протоколзадержания", "задержанвпорядкест91"],
    "постановление_о_продлении": ["постановлениеопродлениисрока", "продлитьсроксодержанияподстражей", "продлитьсрокпредварительногоследствия"],
}


def _collapse(text):
    if not text:
        return ""
    return re.sub(r"\s+", "", text.lower())


def detect_doc_type(text):
    collapsed = _collapse(text)
    best_type = "неизвестный"
    best_score = 0

    for doc_type, markers in DOC_TYPE_MARKERS.items():
        score = sum(1 for m in markers if m in collapsed)
        if score > best_score:
            best_score = score
            best_type = doc_type

    return best_type, best_score


# ==========================================
# ИЗВЛЕЧЕНИЕ ДАТ
# ==========================================
_RE_DATE_DOT = re.compile(r"(\d{1,2})[\.\s](\d{1,2})[\.\s](\d{4})")
_RE_DATE_TEXT = re.compile(
    r"[«\"']?(\d{1,2})[»\"']?\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+(\d{4})",
    re.I
)
_MONTHS = {"января":1,"февраля":2,"марта":3,"апреля":4,"мая":5,"июня":6,
           "июля":7,"августа":8,"сентября":9,"октября":10,"ноября":11,"декабря":12}


def _parse_date(s):
    if not s:
        return None
    m = _RE_DATE_DOT.search(s)
    if m:
        try:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 1900 < y < 2100 and 1 <= mo <= 12 and 1 <= d <= 31:
                return date(y, mo, d)
        except ValueError:
            pass
    m = _RE_DATE_TEXT.search(s)
    if m:
        try:
            d = int(m.group(1))
            mo = _MONTHS.get(m.group(2).lower())
            y = int(m.group(3))
            if mo and 1900 < y < 2100 and 1 <= d <= 31:
                return date(y, mo, d)
        except ValueError:
            pass
    return None


def _find_date_near(text, keywords, window=500):
    low = text.lower()
    for kw in keywords:
        pattern = re.escape(kw).replace(r"\ ", r"\s+")
        m = re.search(pattern, low, re.IGNORECASE)
        if m:
            start = max(0, m.start() - 150)
            end = min(len(text), m.end() + window)
            snippet = text[start:end]
            d = _parse_date(snippet)
            if d:
                return d
    return None


def extract_key_dates(text):
    result = {
        "date_document": None,
        "date_crime": None,
        "date_detention": None,
        "date_mera_pres": None,
        "date_charge": None,
        "date_extension": None,
        "date_final": None,
    }

    result["date_document"] = _parse_date(text)

    result["date_crime"] = _find_date_near(
        text,
        ["совершил", "совершила", "в период времени", "преступление совершено", "умышленно"],
        window=600
    )

    result["date_detention"] = _find_date_near(
        text,
        ["задержан", "задержания", "в порядке ст. 91", "фактического задержания"],
        window=400
    )

    result["date_mera_pres"] = _find_date_near(
        text,
        ["избрать меру пресечения", "избрании меры пресечения", "заключение под стражу",
         "подписка о невыезде", "домашний арест"],
        window=400
    )

    result["date_charge"] = _find_date_near(
        text,
        ["привлечь в качестве обвиняемого", "предъявлено обвинение", "обвинение предъявлено"],
        window=400
    )

    result["date_extension"] = _find_date_near(
        text,
        ["продлить срок", "продлении срока", "продление срока"],
        window=400
    )

    result["date_final"] = _find_date_near(
        text,
        ["направить в суд", "направлено прокурору", "окончание предварительного следствия",
         "обвинительное заключение утверждено"],
        window=400
    )

    if not result["date_final"] and result["date_document"]:
        result["date_final"] = result["date_document"]

    return result