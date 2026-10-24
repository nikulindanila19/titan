# -*- coding: utf-8 -*-
"""
penalty_checker.py — Проверка назначенного наказания
на соответствие санкции статьи и нормам Общей части УК РФ.
"""
import re
from dataclasses import dataclass, field
from typing import Dict, Any

import uk_parser


@dataclass
class CheckResult:
    rule_id: str
    rule_name: str
    status: str
    message: str
    source: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


_RE_SANCTION_BLOCK = re.compile(r"наказывается?\s+([\s\S]{0,800}?)(?=\.|$)", re.IGNORECASE)
_RE_LIFE = re.compile(r"пожизненн", re.I)
_RE_DEATH = re.compile(r"смертн\w+\s+казн", re.I)
_RE_LIBERTY = re.compile(r"лишени\w+\s+свободы", re.I)
_RE_LIBERTY_RANGE = re.compile(r"(?:на\s+срок\s+)?от\s+(\d+(?:[,.]\d+)?)\s+до\s+(\d+(?:[,.]\d+)?)\s*(?:лет|года|год)", re.I)
_RE_LIBERTY_UPTO = re.compile(r"(?:на\s+срок\s+)?до\s+(\d+(?:[,.]\d+)?)\s*(?:лет|года|год)", re.I)
_RE_LIBERTY_EXACT = re.compile(r"(?:на\s+срок\s+)(\d+(?:[,.]\d+)?)\s*(?:лет|года|год)", re.I)
_RE_FINE = re.compile(r"штраф", re.I)
_RE_FINE_AMOUNT = re.compile(r"штраф\w*[\s\S]{0,150}?(?:в\s+размере\s+)?(?:от\s+)?(\d[\d\s]*)\s*(?:до\s+(\d[\d\s]*))?\s*руб", re.I)
_RE_WORKS = re.compile(r"обязательн\w+\s+работ", re.I)
_RE_WORKS_HOURS = re.compile(r"обязательн\w+\s+работ[\s\S]{0,200}?(?:на\s+срок\s+)?от\s+(\d+)\s+до\s+(\d+)\s*час", re.I)
_RE_CORRECTIONAL = re.compile(r"исправительн\w+\s+работ", re.I)
_RE_RESTRICTION = re.compile(r"ограничени\w+\s+свободы", re.I)


def _to_float(s):
    try:
        return float(s.replace(",", ".").replace(" ", ""))
    except (ValueError, AttributeError):
        return None


def parse_sanction(article_text):
    result = {
        "type": "unknown", "min_years": None, "max_years": None,
        "fine_min": None, "fine_max": None, "hours_min": None, "hours_max": None,
        "life": False, "death": False, "raw": article_text[:500] if article_text else "",
    }
    if not article_text:
        return result
    block_m = _RE_SANCTION_BLOCK.search(article_text)
    block = block_m.group(1) if block_m else article_text
    result["life"] = bool(_RE_LIFE.search(block))
    result["death"] = bool(_RE_DEATH.search(block))
    if _RE_LIBERTY.search(block):
        result["type"] = "liberty"
        m_range = _RE_LIBERTY_RANGE.search(block)
        if m_range:
            result["min_years"] = _to_float(m_range.group(1))
            result["max_years"] = _to_float(m_range.group(2))
            return result
        m_upto = _RE_LIBERTY_UPTO.search(block)
        if m_upto:
            result["min_years"] = 0.0
            result["max_years"] = _to_float(m_upto.group(1))
            return result
        m_exact = _RE_LIBERTY_EXACT.search(block)
        if m_exact:
            val = _to_float(m_exact.group(1))
            result["min_years"] = result["max_years"] = val
        return result
    if _RE_FINE.search(block):
        result["type"] = "fine"
        m = _RE_FINE_AMOUNT.search(block)
        if m:
            result["fine_min"] = int(re.sub(r"\s", "", m.group(1))) if m.group(1) else None
            result["fine_max"] = int(re.sub(r"\s", "", m.group(2))) if m.group(2) else result["fine_min"]
        return result
    if _RE_WORKS.search(block):
        result["type"] = "works"
        m = _RE_WORKS_HOURS.search(block)
        if m:
            result["hours_min"] = int(m.group(1))
            result["hours_max"] = int(m.group(2))
        return result
    if _RE_CORRECTIONAL.search(block):
        result["type"] = "correctional"
        return result
    if _RE_RESTRICTION.search(block):
        result["type"] = "restriction"
        return result
    return result


_NEGATIONS = ["не ", "нет ", "без ", "отсутств", "не подтвержд", "не установлен",
              "не в состоянии", "не является", "не имеет", "не усматрива", "не находит",
              "не имеется", "не подлежит", "не может", "не было"]


def _has_negation(text, pos):
    window = text[max(0, pos - 40):pos].lower()
    return any(n in window for n in _NEGATIONS)


def _pick_main_sentence(person_sentences):
    if not person_sentences:
        return None
    for ps in person_sentences:
        if ps.get("type") == "Лишение свободы":
            return ps
    return person_sentences[0]


def check_sanction(sentence, sanction):
    if not sentence or not sanction:
        return CheckResult("sanction", "Санкция статьи", "skipped", "Нет данных о наказании или санкции статьи.")
    if sanction.get("type") == "unknown" or sanction.get("max_years") is None:
        return CheckResult("sanction", "Санкция статьи", "skipped",
                           "Не удалось точно определить санкцию статьи (парсер не нашёл блок). "
                           "Проверьте, что в laws/УК_РФ.txt есть текст статьи.",
                           details={"sanction": sanction, "sentence": sentence})
    if sanction["type"] != "liberty":
        return CheckResult("sanction", "Санкция статьи", "info",
                           f"Вид наказания по приговору: {sentence.get('type')}. "
                           f"Санкция статьи: {sanction['type']}. Детальная сверка не выполнена.",
                           details={"sanction": sanction, "sentence": sentence})
    years = sentence.get("years")
    if years is None:
        return CheckResult("sanction", "Санкция статьи", "skipped", "Срок лишения свободы не распознан в приговоре.")
    max_y = sanction.get("max_years")
    min_y = sanction.get("min_years")
    problems = []
    if max_y is not None and years > max_y + 0.01:
        problems.append(f"назначено {years:.1f} лет, а максимум по санкции — {max_y:.1f} лет")
    if min_y is not None and years < min_y - 0.01:
        problems.append(f"назначено {years:.1f} лет, а минимум по санкции — {min_y:.1f} лет")
    if problems:
        return CheckResult("sanction", "Санкция статьи", "error",
                           "Наказание выходит за пределы санкции статьи: " + "; ".join(problems),
                           source="Санкция статьи УК РФ",
                           details={"years": years, "min": min_y, "max": max_y, "sanction": sanction})
    return CheckResult("sanction", "Санкция статьи", "ok",
                       f"Наказание {years:.1f} лет в пределах санкции "
                       f"({min_y if min_y is not None else '?'}–{max_y if max_y is not None else '?'} лет).",
                       source="Санкция статьи УК РФ",
                       details={"years": years, "min": min_y, "max": max_y})


def check_art56_ch1_enhanced(sentence, article_num, part_num, aggravating, article_text):
    if not sentence or sentence.get("type") != "Лишение свободы":
        return CheckResult("art56_ch1", "Ст. 56 ч. 1 УК РФ", "skipped", "Наказание не связано с лишением свободы.")
    from engines.law_engine import get_sanction_by_part
    sanction = get_sanction_by_part(article_num, part_num)
    if not sanction or not sanction.get("max_years"):
        return CheckResult("art56_ch1", "Ст. 56 ч. 1 УК РФ", "skipped", "Не удалось определить санкцию статьи.")
    max_y = sanction["max_years"]
    if max_y <= 3:
        category = "небольшой тяжести"
    elif max_y <= 5:
        category = "средней тяжести"
    elif max_y <= 10:
        category = "тяжкое"
    else:
        category = "особо тяжкое"
    if category in ("небольшой тяжести", "средней тяжести") and not aggravating:
        exceptions = ["228", "231", "233"]
        if str(article_num) in exceptions:
            return CheckResult("art56_ch1", "Ст. 56 ч. 1 УК РФ", "ok",
                               f"Исключение для ст. {article_num} (ч. 1 ст. 56 УК РФ).")
        return CheckResult(
            "art56_ch1", "Ст. 56 ч. 1 УК РФ", "warning",
            f"Назначено лишение свободы за преступление {category} тяжести "
            f"при отсутствии отягчающих обстоятельств. Требуется проверка исключений по ст. 56 ч. 1 УК РФ.",
            source="Ст. 56 ч. 1 УК РФ"
        )
    return CheckResult("art56_ch1", "Ст. 56 ч. 1 УК РФ", "ok",
                       f"Ограничения ст. 56 ч. 1 УК РФ не нарушены (категория: {category}).")


def check_art62_ch5(sentence, sanction, text):
    low = (text or "").lower()
    is_special = ("особом порядке" in low or "гл. 40" in low or "главе 40" in low or "особый порядок" in low)
    if not is_special:
        return CheckResult("art62_ch5", "Ст. 62 ч. 5 УК РФ", "skipped", "Особый порядок судебного разбирательства не обнаружен.")
    idx = low.find("особ")
    if idx != -1 and _has_negation(low, idx):
        return CheckResult("art62_ch5", "Ст. 62 ч. 5 УК РФ", "skipped", "Особый порядок не применялся (есть отрицание).")
    if not sentence or sentence.get("type") != "Лишение свободы":
        return CheckResult("art62_ch5", "Ст. 62 ч. 5 УК РФ", "skipped", "Наказание не связано с лишением свободы.")
    max_y = sanction.get("max_years") if sanction else None
    years = sentence.get("years")
    if max_y is None or years is None:
        return CheckResult("art62_ch5", "Ст. 62 ч. 5 УК РФ", "skipped", "Недостаточно данных для проверки.")
    limit = max_y * 2 / 3
    if years > limit + 0.01:
        return CheckResult("art62_ch5", "Ст. 62 ч. 5 УК РФ", "error",
                           f"При особом порядке срок не может превышать 2/3 максимума ({limit:.1f} лет), а назначено {years:.1f} лет.",
                           source="Ст. 62 ч. 5 УК РФ",
                           details={"years": years, "max": max_y, "limit": limit})
    return CheckResult("art62_ch5", "Ст. 62 ч. 5 УК РФ", "ok", f"Срок {years:.1f} лет не превышает 2/3 максимума ({limit:.1f} лет).")


def check_art66(sentence, sanction, text):
    low = (text or "").lower()
    is_attempt = "покушени" in low
    is_prep = "приготовлени" in low
    if not (is_attempt or is_prep):
        return CheckResult("art66", "Ст. 66 УК РФ", "skipped", "Признаки неоконченного преступления не обнаружены.")
    if not sentence or sentence.get("type") != "Лишение свободы":
        return CheckResult("art66", "Ст. 66 УК РФ", "skipped", "Наказание не связано с лишением свободы.")
    max_y = sanction.get("max_years") if sanction else None
    years = sentence.get("years")
    if max_y is None or years is None:
        return CheckResult("art66", "Ст. 66 УК РФ", "skipped", "Недостаточно данных для проверки.")
    limit = max_y * (0.5 if is_attempt else 0.75)
    label = "покушения (1/2)" if is_attempt else "приготовления (3/4)"
    if years > limit + 0.01:
        return CheckResult("art66", "Ст. 66 УК РФ", "error",
                           f"Срок за {label} не может превышать {limit:.1f} лет, а назначено {years:.1f} лет.",
                           source="Ст. 66 УК РФ",
                           details={"years": years, "max": max_y, "limit": limit, "stage": label})
    return CheckResult("art66", "Ст. 66 УК РФ", "ok", f"Срок {years:.1f} лет не превышает предела для {label} ({limit:.1f} лет).")


def check_art68(sentence, sanction, aggravating):
    has_recidivism = any("рецидив" in a.lower() for a in (aggravating or []))
    if not has_recidivism:
        return CheckResult("art68", "Ст. 68 УК РФ", "skipped", "Рецидив не обнаружен в отягчающих обстоятельствах.")
    if not sentence or sentence.get("type") != "Лишение свободы":
        return CheckResult("art68", "Ст. 68 УК РФ", "skipped", "Наказание не связано с лишением свободы.")
    max_y = sanction.get("max_years") if sanction else None
    years = sentence.get("years")
    if max_y is None or years is None:
        return CheckResult("art68", "Ст. 68 УК РФ", "skipped", "Недостаточно данных для проверки.")
    limit = max_y / 3
    if years < limit - 0.01:
        return CheckResult("art68", "Ст. 68 УК РФ", "warning",
                           f"При рецидиве срок не может быть менее 1/3 максимума ({limit:.1f} лет), а назначено {years:.1f} лет. "
                           f"Возможно применение ст. 64 УК РФ — требуется мотивировка.",
                           source="Ст. 68 ч. 2 УК РФ",
                           details={"years": years, "max": max_y, "limit": limit})
    return CheckResult("art68", "Ст. 68 УК РФ", "ok", f"Срок {years:.1f} лет не ниже 1/3 максимума ({limit:.1f} лет).")


def check_art64(sentence, sanction, text):
    low = (text or "").lower()
    low = re.sub(r"\s+", " ", low)
    real_markers = [
        "с применением ст. 64", "с применением статьи 64",
        "назначить ниже низшего", "назначение ниже низшего",
        "применить ст. 64", "применить статью 64", "ниже низшего предела",
    ]
    idx = -1
    for marker in real_markers:
        idx = low.find(marker)
        if idx != -1:
            break
    if idx == -1:
        return CheckResult("art64", "Ст. 64 УК РФ", "skipped",
                           "Применение ст. 64 УК РФ не заявлено (только упоминание без применения).")
    if _has_negation(low, idx) or "не усматрива" in low[max(0, idx-80):idx+80] or "не находит" in low[max(0, idx-80):idx+80]:
        return CheckResult("art64", "Ст. 64 УК РФ", "skipped", "Суд не усмотрел оснований для применения ст. 64 УК РФ.")
    if not sentence or sentence.get("type") != "Лишение свободы":
        return CheckResult("art64", "Ст. 64 УК РФ", "info", "Заявлено применение ст. 64 УК РФ. Требуется проверка мотивировки.")
    min_y = sanction.get("min_years") if sanction else None
    years = sentence.get("years")
    if min_y is not None and years is not None and years < min_y - 0.01:
        return CheckResult("art64", "Ст. 64 УК РФ", "info",
                           f"Назначено {years:.1f} лет ниже минимума санкции ({min_y:.1f} лет). "
                           f"Применение ст. 64 УК РФ требует развернутой мотивировки в приговоре.",
                           source="Ст. 64 УК РФ",
                           details={"years": years, "min": min_y})
    return CheckResult("art64", "Ст. 64 УК РФ", "ok", "Применение ст. 64 УК РФ заявлено, но срок не выходит за нижнюю границу.")


def check_mandatory_additional(sentence_text, article_text):
    art_low = (article_text or "").lower()
    sent_low = (sentence_text or "").lower()
    mandatory_patterns = [
        (r"с лишением права занимать определенные должности или заниматься определенной деятельностью",
         "лишение права занимать должности"),
        (r"со штрафом", "штраф"),
    ]
    for pattern, label in mandatory_patterns:
        if re.search(pattern, art_low) and "или без такового" not in art_low:
            if label not in sent_low and "лишен" not in sent_low:
                return CheckResult(
                    "mandatory_additional", "Обязательное дополнительное наказание", "error",
                    f"Санкция статьи предусматривает обязательное дополнительное наказание ({label}), "
                    f"но в приговоре оно не назначено.",
                    source="Санкция статьи УК РФ"
                )
    return CheckResult(
        "mandatory_additional", "Обязательное дополнительное наказание", "ok",
        "Обязательные дополнительные наказания назначены (или не предусмотрены санкцией)."
    )


def check_penalty(text, entities, article_text, article_number):
    results = []
    sanction = parse_sanction(article_text)
    sentence = _pick_main_sentence(entities.get("person_sentences", []))
    aggravating = entities.get("aggravating", [])
    if sentence is None:
        results.append(CheckResult("no_sentence", "Наказание", "skipped", "Не удалось извлечь назначенное наказание из текста."))
        return results
    art_num = ""
    part_num = None
    if article_number:
        art_num = article_number.split()[0].split(".")[0]
        if "ч." in article_number:
            try:
                part_num = article_number.split("ч.")[1].strip().split()[0]
            except Exception:
                pass
    from engines.law_engine import get_sanction_by_part
    precise_sanction = get_sanction_by_part(art_num, part_num)
    if precise_sanction and precise_sanction.get("max_years"):
        sanction = precise_sanction
    results.append(check_sanction(sentence, sanction))
    results.append(check_art56_ch1_enhanced(sentence, art_num, part_num, aggravating, article_text))
    results.append(check_art62_ch5(sentence, sanction, text))
    results.append(check_art66(sentence, sanction, text))
    results.append(check_art68(sentence, sanction, aggravating))
    results.append(check_art64(sentence, sanction, text))
    results.append(check_mandatory_additional(text, article_text))
    return results