# -*- coding: utf-8 -*-
"""
report_engine.py — Формирование итогового заключения по проекту судебного акта.
"""
from datetime import datetime
from penalty_checker import check_penalty


def _status_icon(status):
    return {
        "ok": "✅",
        "warning": "⚠️",
        "error": "❌",
        "info": "ℹ️",
        "skipped": "➖",
    }.get(status, "•")


def _format_checks(checks):
    lines = []
    for c in checks:
        icon = _status_icon(c.status)
        lines.append(f"{icon} {c.rule_name}: {c.message}")
        if c.source:
            lines.append(f"    → {c.source}")
    return "\n".join(lines)


def _collect_problems(checks):
    problems = []
    for c in checks:
        if c.status in ("error", "warning"):
            problems.append(f"{_status_icon(c.status)} {c.rule_name}: {c.message}")
    return problems


def build_report(
    case_title,
    text,
    entities,
    article_text,
    article_number,
    stats=None,
    high_court_positions=None,
    doc_type="неизвестный",
):
    now = datetime.now().strftime("%d.%m.%Y %H:%M")

    # 1. Аннотация
    persons = entities.get("persons", [])
    sentences = entities.get("person_sentences", [])
    articles = entities.get("crime_article", [])
    mitigating = entities.get("mitigating", [])
    aggravating = entities.get("aggravating", [])

    annotation_lines = [
        f"📄 Дело: {case_title}",
        f"📅 Дата формирования заключения: {now}",
        "",
        "👤 Лица:",
    ]
    if persons:
        for p in persons[:10]:
            annotation_lines.append(f"  • {p.get('role', '?')}: {p.get('name', '?')}")
    else:
        annotation_lines.append("  • Не найдены")

    annotation_lines.append("")
    annotation_lines.append("⚖️ Квалификация:")
    if articles:
        annotation_lines.append(f"  • Статьи: {', '.join(articles)}")
    else:
        annotation_lines.append("  • Не найдены")

    annotation_lines.append("")
    annotation_lines.append("⏳ Наказание:")
    
    # Если документ не приговор — наказание не назначалось
    if doc_type != "приговор":
        annotation_lines.append(f"  • Наказание не назначалось (тип документа: {doc_type})")
    else:
        if sentences:
            for s in sentences[:5]:
                if s.get("years"):
                    annotation_lines.append(f"  • {s['name']}: {s['type']}, {s['years']:.1f} лет")
                elif s.get("hours"):
                    annotation_lines.append(f"  • {s['name']}: {s['type']}, {s['hours']} часов")
                elif s.get("fine"):
                    annotation_lines.append(f"  • {s['name']}: {s['type']}, {s['fine']} руб.")
                else:
                    annotation_lines.append(f"  • {s['name']}: {s['type']}")
        else:
            annotation_lines.append("  • Не найдены")

    annotation_lines.append("")
    annotation_lines.append("🟢 Смягчающие:")
    annotation_lines.append("  • " + (", ".join(mitigating) if mitigating else "не найдены"))
    annotation_lines.append("🔴 Отягчающие:")
    annotation_lines.append("  • " + (", ".join(aggravating) if aggravating else "не найдены"))

    # 2. Проверка
    check_lines = ["", "=" * 60, "🔍 РЕЗУЛЬТАТ ПРОВЕРКИ НА СООТВЕТСТВИЕ ЗАКОНУ", "=" * 60]
    
    if doc_type == "приговор":
        checks = check_penalty(text, entities, article_text, article_number)
        problems = _collect_problems(checks)
        check_lines.append(_format_checks(checks))
    else:
        problems = []
        check_lines.append(
            f"➖ Проверка санкции и правил Общей части УК РФ не применима: "
            f"документ не является приговором (тип: {doc_type}).\n"
            f"   На данном этапе проверяется только квалификация и процессуальные сроки."
        )

    # 3. Области для анализа
    analysis_lines = ["", "=" * 60, "🧐 ПОТЕНЦИАЛЬНЫЕ ОБЛАСТИ ДЛЯ ГЛУБОКОГО АНАЛИЗА", "=" * 60]
    if problems:
        analysis_lines.append("Обнаружены следующие моменты, требующие внимания:")
        for p in problems:
            analysis_lines.append(f"  {p}")
    else:
        analysis_lines.append("Формальных несоответствий не обнаружено.")

    if high_court_positions:
        analysis_lines.append("")
        analysis_lines.append("Правовые позиции ВС/КС, которые стоит учесть:")
        for i, pos in enumerate(high_court_positions[:5], 1):
            analysis_lines.append(f"  {i}. {pos}")

    # 4. Статистика
    stats_lines = ["", "=" * 60, "📊 СТАТИСТИЧЕСКАЯ СПРАВКА ПО АНАЛОГИЧНЫМ ПРИГОВОРАМ", "=" * 60]
    if stats and stats.get("message"):
        stats_lines.append(stats["message"])
    else:
        stats_lines.append("Статистика по аналогичным приговорам не запрашивалась.")

    # 5. Дисклеймер
    disclaimer_lines = [
        "",
        "=" * 60,
        "⚠️ ВАЖНО",
        "=" * 60,
        "Настоящее заключение сформировано автоматически и носит исключительно",
        "вспомогательный характер. Оно не является юридическим заключением,",
        "не замещает судью в процессе правоприменения и требует обязательной",
        "проверки со стороны судьи (или иного уполномоченного лица).",
    ]

    # Собираем всё вместе
    report = "\n".join(
        annotation_lines
        + check_lines
        + analysis_lines
        + stats_lines
        + disclaimer_lines
    )
    return report