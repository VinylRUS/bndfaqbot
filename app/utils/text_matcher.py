from __future__ import annotations

from typing import Optional, List

from app.database.models.auto_answer import AutoAnswer


def normalize_text(text: str) -> str:
    return text.lower().strip()


def find_matching_auto_answer(
    user_text: str,
    auto_answers: List[AutoAnswer],
) -> Optional[AutoAnswer]:
    normalized = normalize_text(user_text)

    for auto_answer in auto_answers:
        if not auto_answer.is_active:
            continue
        keywords = [normalize_text(kw) for kw in auto_answer.keywords.split(",")]
        for keyword in keywords:
            if keyword and keyword in normalized:
                return auto_answer

    return None
