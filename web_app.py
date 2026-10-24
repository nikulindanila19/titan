# -*- coding: utf-8 -*-
"""
web_app.py — Веб-интерфейс системы «Титан» на Streamlit.
Запуск: streamlit run web_app.py
"""
import os
import json
import tempfile
import re
import streamlit as st
from datetime import datetime

# ==========================================
# ИМПОРТЫ (исправлены под структуру проекта)
# ==========================================
# Файлы из папки engines
from engines.doc_engine import read_document
from engines.ner_engine import extract_entities
from engines.science_engine import detect_case_type, analyze_legal_science, format_science_report
from engines.ai_engine import ai
from engines.settings_manager import load_settings, save_settings
from engines.law_engine import get_sanction_by_part

# Файлы из корня проекта
from penalty_checker import check_penalty
from report_engine import build_report
from doc_type_engine import detect_doc_type, extract_key_dates
from upk_timing_checker import check_timing, format_timing_block
from plenum_matcher import find_relevant_positions, format_positions_block
from court_stats import get_similar_cases_stats
import uk_parser


# ==========================================
# НАСТРОЙКИ СТРАНИЦЫ
# ==========================================
st.set_page_config(
    page_title="Система «Титан» — Юридический анализатор",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Файл для хранения истории
HISTORY_FILE = os.path.join("data", "web_history.json")
os.makedirs("data", exist_ok=True)


def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def get_article_sanction_text(article_number):
    """Извлекает текст статьи из базы законов (УК_РФ.txt)."""
    if not article_number:
        return ""
    law_file = uk_parser.ACTIVE_LAW_FILE
    if not law_file:
        return ""
    txt_path = os.path.join(uk_parser.LAWS_DIR, law_file.replace(".json", ".txt"))
    if not os.path.exists(txt_path):
        return ""
    try:
        with open(txt_path, "r", encoding="utf-8") as f:
            full_text = f.read()
        base_art = article_number.split(" ")[0].split(".")[0]
        m = re.search(rf"(Статья\s+{re.escape(base_art)}[\s\S]*?)(?=Статья\s+\d+|$)", full_text, re.IGNORECASE)
        return m.group(1)[:3000] if m else ""
    except Exception:
        return ""


# ==========================================
# БОКОВАЯ ПАНЕЛЬ (ЛИЧНЫЙ КАБИНЕТ)
# ==========================================
with st.sidebar:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=100)
    st.title("Система «Титан»")
    st.caption("Юридический анализатор судебных актов")
    
    st.divider()
    
    # Навигация
    page = st.radio("Навигация", ["🏠 Личный кабинет", "⚖️ Рабочая область анализа"])
    
    st.divider()
    
    # Настройки API
    with st.expander("⚙️ Настройки API"):
        settings = load_settings()
        or_key = st.text_input("OpenRouter API Key", value=settings.get("openrouter_api_key", ""), type="password")
        ds_key = st.text_input("DeepSeek API Key", value=settings.get("deepseek_api_key", ""), type="password")
        if st.button("💾 Сохранить ключи"):
            settings["openrouter_api_key"] = or_key
            settings["deepseek_api_key"] = ds_key
            save_settings(settings)
            ai.reload_settings()
            st.success("Ключи сохранены!")
    
    st.divider()
    st.caption("© РГУП им. В.М. Лебедева, 2026")

# ==========================================
# ЛИЧНЫЙ КАБИНЕТ
# ==========================================
if page == "🏠 Личный кабинет":
    st.header("🏠 Личный кабинет")
    st.write("Здесь хранится история ваших анализов.")
    
    history = load_history()
    
    if not history:
        st.info("История пуста. Перейдите в «Рабочую область анализа», чтобы загрузить первый документ.")
    else:
        for i, item in enumerate(reversed(history)):
            with st.expander(f"📄 {item['filename']} — {item['date']}"):
                st.write(f"**Тип документа:** {item.get('doc_type', 'неизвестен')}")
                st.write(f"**Статьи:** {', '.join(item.get('articles', [])) or 'не найдены'}")
                st.write(f"**Лица:** {', '.join(item.get('persons', [])) or 'не найдены'}")
                if st.button("🗑️ Удалить из истории", key=f"del_{i}"):
                    history.remove(item)
                    save_history(history)
                    st.rerun()

# ==========================================
# РАБОЧАЯ ОБЛАСТЬ АНАЛИЗА
# ==========================================
elif page == "⚖️ Рабочая область анализа":
    st.header("⚖️ Рабочая область анализа")
    
    uploaded_file = st.file_uploader(
        "Загрузите проект судебного акта",
        type=["pdf", "docx", "doc", "txt", "jpg", "jpeg", "png", "bmp", "tiff"]
    )
    
    if uploaded_file is not None:
        # Сохраняем файл во временную папку
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = tmp.name
        
        st.success(f"Файл загружен: {uploaded_file.name}")
        
        if st.button("🚀 Начать анализ", type="primary"):
            with st.spinner("Анализирую документ..."):
                try:
                    # 1. Читаем текст
                    text = read_document(tmp_path)
                    if not text:
                        st.error("Не удалось прочитать документ. Возможно, файл повреждён или это картинка без текста.")
                        st.stop()
                    
                    # 2. Извлекаем сущности
                    ents = extract_entities(text)
                    articles = ents.get("crime_article", [])
                    main_article = articles[0] if articles else ""
                    
                    # 3. Определяем тип документа и сроки
                    doc_type, confidence = detect_doc_type(text)
                    key_dates = extract_key_dates(text)
                    timing_results = check_timing(key_dates, doc_type)
                    timing_block = format_timing_block(timing_results)
                    
                    # 4. Ищем правовые позиции Пленума
                    plenum_positions = find_relevant_positions(articles, text)
                    plenum_block = format_positions_block(plenum_positions)
                    
                    # 5. Извлекаем текст статьи из базы законов
                    article_text = get_article_sanction_text(main_article)
                    
                    # 6. Статистика по аналогичным приговорам
                    stats = None
                    try:
                        sentences = ents.get("person_sentences", [])
                        cur_years = next((s.get("years") for s in sentences if s.get("years")), None)
                        stats = get_similar_cases_stats(main_article, current_sentence_years=cur_years)
                    except Exception:
                        pass
                    
                    # 7. Формируем отчет
                    report = build_report(
                        case_title=uploaded_file.name,
                        text=text,
                        entities=ents,
                        article_text=article_text,
                        article_number=main_article,
                        stats=stats,
                        high_court_positions=None,
                        doc_type=doc_type,
                    )
                    
                    # 8. Добавляем научный анализ
                    science_result = analyze_legal_science(text, articles)
                    science_text = format_science_report(science_result)
                    
                    full_report = f"📋 Тип документа: {doc_type} (уверенность: {confidence})\n\n" + report
                    if plenum_block:
                        full_report += "\n" + plenum_block
                    if timing_block:
                        full_report += "\n" + timing_block
                    full_report += "\n\n" + "=" * 60 + "\n" + science_text
                    
                    # 9. Выводим отчет
                    st.subheader("📊 Результат анализа")
                    st.text(full_report)  # st.text сохраняет все переносы строк и отступы
                    
                    # 10. Сохраняем в историю
                    history = load_history()
                    history.append({
                        "filename": uploaded_file.name,
                        "date": datetime.now().strftime("%d.%m.%Y %H:%M"),
                        "doc_type": doc_type,
                        "articles": articles,
                        "persons": [p["name"] for p in ents.get("persons", [])],
                    })
                    save_history(history)
                    
                    # 11. Кнопка для скачивания отчета
                    st.download_button(
                        label="📥 Скачать отчет (.txt)",
                        data=full_report,
                        file_name=f"report_{uploaded_file.name}.txt",
                        mime="text/plain"
                    )
                    
                except Exception as e:
                    st.error(f"Ошибка анализа: {e}")
                finally:
                    # Удаляем временный файл
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
    else:
        st.info("Загрузите файл, чтобы начать анализ.")