# -*- coding: utf-8 -*-
"""
plenum_matcher.py — Сопоставление приговора с базой правовых позиций Пленума ВС РФ.
Берет текст приговора, находит статьи и маркеры ситуаций,
возвращает релевантные правовые позиции.
"""
import os
import json
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
POSITIONS_FILE = os.path.join(DATA_DIR, "legal_positions.json")

_positions_cache = None


def load_positions():
    """Загружает базу правовых позиций (с кэшированием)."""
    global _positions_cache
    if _positions_cache is not None:
        return _positions_cache
    if not os.path.exists(POSITIONS_FILE):
        _positions_cache = {}
        return _positions_cache
    try:
        with open(POSITIONS_FILE, "r", encoding="utf-8") as f:
            _positions_cache = json.load(f)
    except Exception:
        _positions_cache = {}
    return _positions_cache


def _normalize(text):
    return re.sub(r"\s+", " ", (text or "").lower())


def _extract_base_article(article_number):
    """'158 ч.2' -> '158'"""
    if not article_number:
        return None
    m = re.match(r"(\d+(?:\.\d+)?)", str(article_number).strip())
    return m.group(1) if m else None


def find_relevant_positions(article_numbers, text):
    """
    Возвращает список релевантных правовых позиций.

    Параметры:
        article_numbers — список статей (например, ['105 ч.2', '158 ч.1'])
        text — полный текст приговора

    Возвращает:
        [{"id": "...", "position": "...", "source": "...", "matched_marker": "..."}]
    """
    positions_db = load_positions()
    if not positions_db or not article_numbers:
        return []

    low_text = _normalize(text)
    results = []
    seen_ids = set()

    for art in article_numbers:
        base = _extract_base_article(art)
        if not base or base not in positions_db:
            continue
        for item in positions_db[base]:
            item_id = item.get("id")
            if item_id in seen_ids:
                continue
            for marker in item.get("situation_markers", []):
                if _normalize(marker) in low_text:
                    results.append({
                        "id": item_id,
                        "article": base,
                        "position": item.get("position", ""),
                        "source": item.get("source", ""),
                        "matched_marker": marker,
                    })
                    seen_ids.add(item_id)
                    break  # одного маркера достаточно для этой позиции
    return results


def format_positions_block(relevant_positions):
    """Форматирует найденные позиции в текстовый блок."""
    if not relevant_positions:
        return ""
    lines = [
        "",
        "=" * 60,
        "📖 РАЗЪЯСНЕНИЯ ПЛЕНУМА ВЕРХОВНОГО СУДА РФ, РЕЛЕВАНТНЫЕ ДЕЛУ",
        "=" * 60,
    ]
    for i, p in enumerate(relevant_positions, 1):
        lines.append(f"{i}. [{p['source']}]")
        lines.append(f"   {p['position']}")
        lines.append(f"   (Совпавший маркер: «{p['matched_marker']}»)")
        lines.append("")
    return "\n".join(lines)


# ==========================================
# БЫСТРЫЙ ТЕСТ
# ==========================================
if __name__ == "__main__":
    demo_text = (
        "Подсудимый совершил убийство двух лиц с особой жестокостью, "
        "действуя группой лиц по предварительному сговору. "
        "Квалифицировано по п. «а», «д», «ж» ч. 2 ст. 105 УК РФ."
    )
    demo_articles = ["105 ч.2"]
    found = find_relevant_positions(demo_articles, demo_text)
    print(format_positions_block(found))