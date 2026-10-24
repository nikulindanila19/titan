# -*- coding: utf-8 -*-
import os
import re
import json

from engines.perf_engine import get_cached_law_json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LAWS_DIR = os.path.join(BASE_DIR, "laws")

ACTIVE_LAW_FILE = None
if os.path.exists(LAWS_DIR):
    files = sorted(os.listdir(LAWS_DIR))
    for f in files:
        if f.endswith(".json") and "уголовный_кодекс" in f.lower():
            ACTIVE_LAW_FILE = f
            break
    if not ACTIVE_LAW_FILE:
        for f in files:
            if f.endswith(".json"):
                ACTIVE_LAW_FILE = f
                break


def set_active_law(filename):
    global ACTIVE_LAW_FILE
    ACTIVE_LAW_FILE = filename


def load_law_db(filename=None):
    target = filename if filename else ACTIVE_LAW_FILE
    if not target:
        return {}
    path = os.path.join(LAWS_DIR, target)
    return get_cached_law_json(path)


def get_uk_sanction(article_num):
    if article_num is None:
        return None
    m = re.match(r"\d+(?:\.\d+)?", str(article_num).strip())
    if not m:
        return None
    return load_law_db().get(m.group(0))


def get_crime_severity(article_num):
    y = get_uk_sanction(article_num)
    if y is None:
        return None
    if y <= 3: return "Небольшой тяжести"
    if y <= 5: return "Средней тяжести"
    if y <= 10: return "Тяжкое"
    return "Особо тяжкое"


CONSULTANT_DOC_LINKS = {
    "УК_РФ": "https://www.consultant.ru/document/cons_doc_LAW_10699/",
    "УПК_РФ": "https://www.consultant.ru/document/cons_doc_LAW_34481/",
    "ГК_РФ": "https://www.consultant.ru/document/cons_doc_LAW_5142/",
    "ГПК_РФ": "https://www.consultant.ru/document/cons_doc_LAW_39570/",
    "КоАП_РФ": "https://www.consultant.ru/document/cons_doc_LAW_34661/",
    "АПК_РФ": "https://www.consultant.ru/document/cons_doc_LAW_37800/",
    "КАС_РФ": "https://www.consultant.ru/document/cons_doc_LAW_176147/",
}


def search_in_law(query, law_filename=None):
    target_json = law_filename if law_filename else ACTIVE_LAW_FILE
    if not target_json:
        return {"error": "Закон не выбран."}
    target_txt = target_json.replace(".json", ".txt")
    txt_path = os.path.join(LAWS_DIR, target_txt)
    if not os.path.exists(txt_path):
        return {"error": f"Файл {target_txt} не найден."}
    with open(txt_path, "r", encoding="utf-8") as f:
        full_text = f.read()
    q = query.strip()
    if not q:
        return {"error": "Пустой запрос."}
    doc_key = target_json.replace(".json", "").replace(" ", "_")
    doc_link = CONSULTANT_DOC_LINKS.get(doc_key, "https://www.consultant.ru")

    m = re.match(
        r"^(?:ст\.?\s*|статья\s*)?(\d+(?:\.\d+)?)"
        r"(?:\s*(?:ч\.?|часть)\s*(\d+))?"
        r"(?:\s*(?:п\.?|пункт)\s*([а-я\d]+))?"
        r"$",
        q, re.IGNORECASE
    )
    if m:
        art_num = m.group(1)
        part_num = m.group(2)
        db = load_law_db(target_json)
        sanction = db.get(art_num)
        art_match = re.search(
            rf"(Статья\s+{re.escape(art_num)}[\s\S]*?)(?=Статья\s+\d+|$)",
            full_text, re.IGNORECASE
        )
        excerpt = art_match.group(1)[:1500] if art_match else "Текст не найден."
        title = f"Статья {art_num}"
        if part_num:
            title += f", часть {part_num}"
        return {"results": [{"title": title, "text": excerpt, "link": doc_link, "sanction": sanction}]}

    lower_q = q.lower()
    results = []
    for art_block in re.split(r"(?=Статья\s+\d+)", full_text):
        if lower_q in art_block.lower() and len(art_block) > 30:
            lines = art_block.split("\n")
            header = lines[0][:100] if lines else "Статья"
            pos = art_block.lower().find(lower_q)
            start = max(0, pos - 100)
            end = min(len(art_block), pos + len(q) + 200)
            context = art_block[start:end].replace("\n", " ").strip()
            results.append({"title": header, "text": f"...{context}...", "link": doc_link})
            if len(results) >= 5: break

    if results:
        return {"results": results}
    return {"results": [], "message": f"По запросу «{q}» ничего не найдено."}