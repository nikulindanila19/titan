# -*- coding: utf-8 -*-
"""Статистика по аналогичным приговорам: sudact.ru -> DEMO_DB."""
import re
import urllib.parse

try:
    import requests
    from bs4 import BeautifulSoup
    _HAS_REQUESTS = True
except Exception:
    _HAS_REQUESTS = False

DEMO_DB = {
    "158": [1.0, 1.5, 2.0, 1.2, 1.8, 2.5, 1.0, 1.5, 3.0, 1.5, 2.0, 1.8, 2.2, 1.4, 2.0],
    "159": [1.0, 2.0, 1.5, 3.0, 1.2, 1.8, 2.5, 1.0, 1.5, 2.0, 1.6, 2.3, 1.9, 2.1, 1.7],
    "161": [1.5, 2.0, 3.0, 2.5, 1.8, 2.2, 3.5, 2.0, 1.5, 2.8, 2.3, 2.6, 1.9, 2.1, 2.4],
    "162": [3.0, 4.0, 5.0, 3.5, 4.5, 6.0, 3.0, 4.2, 5.5, 4.0, 3.8, 4.6, 3.3, 4.1, 5.2],
    "105": [8.0, 9.0, 10.0, 7.5, 9.5, 11.0, 8.5, 9.0, 12.0, 10.0, 8.8, 9.7, 10.5, 8.2, 9.3],
    "111": [2.0, 3.0, 4.0, 2.5, 3.5, 5.0, 2.0, 3.2, 4.5, 3.0, 2.7, 3.8, 2.3, 3.4, 4.1],
    "228": [3.0, 4.0, 5.0, 3.5, 4.5, 6.0, 3.0, 4.0, 5.5, 4.5, 3.7, 4.3, 3.2, 4.8, 5.1],
    "264": [1.5, 2.0, 3.0, 2.5, 1.8, 2.2, 3.5, 2.0, 1.5, 2.8, 2.1, 2.4, 1.9, 2.6, 2.3],
    "160": [0.5, 0.8, 1.0, 0.6, 0.9, 1.2, 0.7, 1.0, 0.5, 0.8, 1.1, 0.9, 0.6, 1.0, 0.7],
}


def _fetch_from_sudact(article_number, max_results=10):
    if not _HAS_REQUESTS or not article_number:
        return []
    query = f"ст {article_number} УК РФ приговор"
    url = f"https://sudact.ru/regular/doc/?regular-txt={urllib.parse.quote(query)}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        results = []
        for block in soup.find_all("div", class_="regular-doc"):
            text = block.get_text(" ", strip=True)
            for y in re.findall(r"(\d+(?:[,.]\d+)?)\s*(?:лет|года|год)\s+лишени", text, re.IGNORECASE):
                try:
                    results.append(float(y.replace(",", ".")))
                except ValueError:
                    pass
            if len(results) >= max_results:
                break
        return results[:max_results]
    except Exception:
        return []


def get_similar_cases_stats(article_number, current_sentence_years=None, max_results=10):
    if not article_number:
        return None
    m = re.match(r"\d+", str(article_number).strip())
    if not m:
        return None
    num = m.group(0)

    try:
        cur = float(current_sentence_years) if current_sentence_years is not None else None
    except (TypeError, ValueError):
        cur = None

    samples = _fetch_from_sudact(num, max_results=max_results)
    source = "sudact.ru"
    if not samples:
        samples = DEMO_DB.get(num, [])
        source = "Демо-база"

    if not samples:
        return {
            "source": "Нет данных", "article": num, "sample_size": 0,
            "samples": [], "avg": None, "min": None, "max": None,
            "deviation": None, "message": f"Нет данных по ст. {num}.",
        }

    avg = sum(samples) / len(samples)
    lo, hi = min(samples), max(samples)
    deviation = (cur - avg) if cur is not None else None

    lines = [
        f"Выборка: {len(samples)} приговоров (источник: {source}).",
        f"Средний срок: {avg:.1f} лет (от {lo:g} до {hi:g}).",
    ]
    if deviation is not None:
        sign = "+" if deviation >= 0 else ""
        lines.append(f"В анализируемом приговоре: {cur:g} лет.")
        lines.append(f"Отклонение от среднего: {sign}{deviation:.1f} лет.")
        if deviation > 1.5:
            lines.append("Вывод: срок существенно ВЫШЕ среднего (требует анализа).")
        elif deviation < -1.5:
            lines.append("Вывод: срок существенно НИЖЕ среднего (требует анализа).")
        else:
            lines.append("Вывод: срок в пределах средних значений.")

    return {
        "source": source, "article": num, "sample_size": len(samples),
        "samples": samples, "avg": avg, "min": lo, "max": hi,
        "deviation": deviation, "message": "\n".join(lines),
    }