"""Chat Agent: 자연어 질문에 DB 검색 기반 답변 (RAG)"""
import json
import re
from utils.llm_client import ask_llm
from utils.prompts import CHAT_AGENT_PROMPT, CALENDAR_REGISTER_PROMPT
from utils.calendar_client import create_calendar_event
from storage.queries import (
    get_meeting_context,
    get_pending_actions,
    get_all_actions,
    get_chat_history,
)


async def chat_response(chat_id: int, message: str, mode: str = "general") -> str:
    """모드별 응답 생성"""
    if mode == "calendar":
        return await _handle_calendar(chat_id, message)
    elif mode == "task":
        return await _handle_task_query(chat_id, message)
    else:
        return await _handle_general_chat(chat_id, message)


async def _handle_general_chat(chat_id: int, message: str) -> str:
    # 키워드로 관련 회의 검색
    keywords = _extract_keywords(message)
    context = await get_meeting_context(chat_id, keyword=keywords)

    prompt = CHAT_AGENT_PROMPT.format(context=context, question=message)

    response = await ask_llm(
        prompt,
        model="claude-sonnet-4-6",
        max_tokens=1500,
    )
    return response.strip()


async def _handle_task_query(chat_id: int, message: str) -> str:
    """할 일 관련 질문 처리"""
    if "완료" in message or "done" in message.lower():
        actions = await get_all_actions(chat_id)
    else:
        actions = await get_pending_actions(chat_id)

    if not actions:
        return "📭 등록된 할 일이 없습니다."

    # 특정 담당자 필터
    assignee_match = re.search(r"([가-힣]{2,5})(의|이|가|님)?.*할\s*일", message)
    if assignee_match:
        name = assignee_match.group(1)
        actions = [a for a in actions if a.get("assignee") and name in a["assignee"]]

    priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}
    lines = [f"📋 *할 일 목록* ({len(actions)}건)\n"]
    for i, a in enumerate(actions, 1):
        emoji = priority_emoji.get(a.get("priority", "medium"), "🟡")
        assignee = a.get("assignee") or "미정"
        deadline = a.get("deadline") or "기한 없음"
        status = "✅" if a.get("status") == "done" else "⬜"
        lines.append(f"{status} {i}. {emoji} {a['description']}")
        lines.append(f"   👤 {assignee}  📅 {deadline}  (ID: {a['id']})")

    lines.append("\n완료 처리: `/done [ID]` 명령어를 사용하세요")
    return "\n".join(lines)


async def _handle_calendar(chat_id: int, message: str) -> str:
    """캘린더 등록 요청 처리"""
    actions = await get_pending_actions(chat_id)
    if not actions:
        return "등록할 할 일이 없습니다. 먼저 회의록을 업로드해주세요."

    prompt = CALENDAR_REGISTER_PROMPT.format(
        action_items=json.dumps(actions, ensure_ascii=False, indent=2),
        request=message,
    )

    try:
        raw = await ask_llm(prompt, max_tokens=1000)
        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            events = json.loads(match.group(0))
        else:
            events = json.loads(raw)
    except Exception:
        return "❌ 캘린더 등록 정보를 파싱하지 못했습니다."

    # 날짜 확인 필요한 항목 처리
    needs_confirm = [e for e in events if e.get("needs_date_confirm")]
    ready = [e for e in events if not e.get("needs_date_confirm") and e.get("date")]

    results = []
    errors = []

    for event in ready:
        try:
            link = await create_calendar_event(
                title=event["title"],
                date=event["date"],
                description=event.get("description", ""),
            )
            results.append(f"✅ {event['title']} ({event['date']})")
        except Exception as e:
            errors.append(f"❌ {event['title']}: {e}")

    response_lines = []
    if results:
        response_lines.append("📅 *캘린더 등록 완료*\n" + "\n".join(results))
    if errors:
        response_lines.append("⚠️ *등록 실패*\n" + "\n".join(errors))
    if needs_confirm:
        titles = [e["title"] for e in needs_confirm]
        response_lines.append(
            f"📌 *날짜 미정 항목* (날짜를 알려주시면 등록합니다)\n" +
            "\n".join(f"• {t}" for t in titles)
        )

    return "\n\n".join(response_lines) if response_lines else "등록할 항목이 없습니다."


def _extract_keywords(message: str) -> str:
    """메시지에서 검색 키워드 추출 (간단한 명사 추출)"""
    # 조사/어미 제거 후 핵심 단어 추출
    stop_words = {"에서", "이야", "이에요", "했지", "했어", "했나", "했는지", "뭐", "어떻게", "언제", "누가"}
    words = re.findall(r"[가-힣]{2,}", message)
    keywords = [w for w in words if w not in stop_words]
    return " ".join(keywords[:3]) if keywords else ""
