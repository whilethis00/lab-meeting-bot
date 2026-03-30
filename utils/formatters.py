"""텔레그램 응답 포맷터 (Markdown V1 기준, 4096자 제한 처리)"""
from typing import Optional


def format_meeting_response(summary: str, actions: list, date: str = "") -> str:
    date_str = date or "오늘"
    lines = [f"✅ *회의록 분석 완료!*\n", f"📋 *{date_str} 랩미팅*\n"]

    lines.append("📝 *요약*")
    lines.append(summary)
    lines.append("")

    if actions:
        lines.append(f"✅ *할 일 ({len(actions)}건)*")
        priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        for i, a in enumerate(actions, 1):
            emoji = priority_emoji.get(a.get("priority", "medium"), "🟡")
            assignee = a.get("assignee") or "미정"
            deadline = a.get("deadline") or "기한 없음"
            desc = a.get("description", "")
            lines.append(f"{i}\\. {emoji} {desc} — {assignee} ({deadline})")
        lines.append("")

    lines.append("💬 질문이 있으면 편하게 물어보세요\\!")
    lines.append("📅 캘린더에 등록하려면 \\'캘린더에 넣어줘\\'라고 말씀해주세요\\.")

    return "\n".join(lines)


def split_long_message(text: str, max_length: int = 4000) -> list[str]:
    """텔레그램 4096자 제한 처리 — 줄 단위로 분할"""
    if len(text) <= max_length:
        return [text]

    chunks = []
    current = []
    current_len = 0

    for line in text.split("\n"):
        line_len = len(line) + 1
        if current_len + line_len > max_length:
            chunks.append("\n".join(current))
            current = [line]
            current_len = line_len
        else:
            current.append(line)
            current_len += line_len

    if current:
        chunks.append("\n".join(current))

    return chunks


def format_task_list(actions: list, title: str = "📋 미완료 할 일") -> str:
    if not actions:
        return "✅ 미완료 할 일이 없습니다\\!"

    lines = [f"*{title}*\n"]
    priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}

    for i, a in enumerate(actions, 1):
        emoji = priority_emoji.get(a.get("priority", "medium"), "🟡")
        assignee = a.get("assignee") or "미정"
        deadline = a.get("deadline") or "기한 없음"
        desc = a.get("description", "")
        status = "✅" if a.get("status") == "done" else "⬜"
        lines.append(f"{status} {i}\\. {emoji} {desc}")
        lines.append(f"   담당: {assignee} \\| 기한: {deadline}")

    return "\n".join(lines)


def format_meeting_list(meetings: list) -> str:
    if not meetings:
        return "저장된 회의록이 없습니다\\."

    lines = ["*📅 최근 회의 목록*\n"]
    for m in meetings:
        date = m.get("date", "날짜 미상")
        title = m.get("title") or f"{date} 랩미팅"
        meeting_id = m.get("id", "")
        lines.append(f"• *{date}* — {title} \\(ID: {meeting_id}\\)")

    return "\n".join(lines)


def escape_markdown(text: str) -> str:
    """MarkdownV1에서 문제가 될 수 있는 특수문자 이스케이프"""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for ch in special_chars:
        text = text.replace(ch, f'\\{ch}')
    return text
