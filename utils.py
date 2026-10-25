from html import escape

from app.schemas import CodeReviewResponse, IssueSeverity

SEVERITY = {
    IssueSeverity.critical: ("🔴", "Критическая"),
    IssueSeverity.high: ("🟠", "Высокая"),
    IssueSeverity.medium: ("🟡", "Средняя"),
    IssueSeverity.low: ("🔵", "Низкая"),
    IssueSeverity.info: ("ℹ️", "Информация"),
}

LEVEL_NAMES = {
    "junior": "Junior",
    "middle": "Middle",
    "senior": "Senior",
}

ISSUES_PER_MESSAGE = 3


def _score_bar(score: int) -> str:
    filled = round(score / 10)
    return "🟩" * filled + "⬜" * (10 - filled)


def _split_code(code: str, limit: int = 3000) -> list[str]:
    if not code:
        return ["Код отсутствует."]

    return [code[index : index + limit] for index in range(0, len(code), limit)]


def _format_issue(index: int, issue) -> str:
    emoji, severity_name = SEVERITY[issue.severity]
    return (
        f"{emoji} <b>Проблема #{index}</b>\n\n"
        f"📌 <b>{escape(issue.title)}</b>\n"
        f"⚡ <b>Серьёзность:</b> {severity_name}\n"
        f"🏷 <b>Категория:</b> {escape(issue.category)}\n"
        f"📍 <b>Строка:</b> {issue.line}\n\n"
        f"<b>Описание</b>\n{escape(issue.description)}\n\n"
        f"💡 <b>Рекомендация</b>\n"
        f"{escape(issue.recommendation)}"
    )


def render_review(review: CodeReviewResponse) -> list[str]:
    level = LEVEL_NAMES.get(review.level, review.level.title())

    messages = [
        (
            "🔍 <b>AI CODE REVIEW</b>\n\n"
            f"🎯 <b>Уровень:</b> {escape(level)}\n"
            f"📊 <b>Оценка:</b> {review.score}/100\n"
            f"{_score_bar(review.score)}\n\n"
            f"📝 <b>Итог</b>\n{escape(review.summary)}\n\n"
            f"🐛 <b>Найдено проблем:</b> {len(review.issues)}"
        )
    ]

    if review.issues:
        blocks = [
            _format_issue(index, issue)
            for index, issue in enumerate(review.issues, start=1)
        ]
        for start in range(0, len(blocks), ISSUES_PER_MESSAGE):
            messages.append(
                "\n\n---\n\n".join(blocks[start : start + ISSUES_PER_MESSAGE])
            )
    else:
        messages.append(
            "✅ <b>Проблем не обнаружено!</b>\n"
            "В рамках проведённой проверки замечаний нет."
        )

    if review.improved_code.strip():
        for index, chunk in enumerate(_split_code(review.improved_code), start=1):
            suffix = f" — часть {index}" if len(review.improved_code) > 3000 else ""
            messages.append(
                f"🛠 <b>Улучшенный код{suffix}</b>\n"
                f"<pre><code>{escape(chunk)}</code></pre>"
            )

    if review.junior_explanation.strip():
        messages.append(f"📚 <b>Объяснение</b>\n\n{escape(review.junior_explanation)}")

    if review.practice_task.strip():
        messages.append(
            f"🚀 <b>Задание для практики</b>\n\n{escape(review.practice_task)}"
        )

    return messages
