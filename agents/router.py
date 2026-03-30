"""Router Agent: 메시지 의도 분류 (규칙 기반 + LLM 혼합)"""
import json
import re
from utils.llm_client import ask_llm
from utils.prompts import ROUTER_PROMPT

# 빠른 규칙 기반 패턴
_TRANSCRIPT_PATTERN = re.compile(r"화자\s*\d+|SPEAKER[_\s]\d+", re.IGNORECASE)
_TIMESTAMP_PATTERN = re.compile(r"\d{1,2}:\d{2}:\d{2}")
_CALENDAR_KEYWORDS = ["캘린더", "일정 등록", "캘린더에 넣", "캘린더에 추가", "구글 캘린더", "일정에 추가"]
_TASK_KEYWORDS = ["할 일", "태스크", "task", "할일", "미완료", "done", "완료 처리"]
_SEARCH_KEYWORDS = ["지난", "이전", "회의에서", "미팅에서", "언제", "뭐라고", "어떻게 됐"]
_NAME_KEYWORDS = ["화자", "이름 설정", "이름은", "setname", "이름 바꿔"]


async def classify_intent(message: str) -> str:
    """메시지 의도를 반환. 하이브리드 방식 (규칙 우선, 애매하면 LLM)."""
    msg_lower = message.lower()

    # 1. 전사본 업로드 규칙 (긴 텍스트 + 화자 패턴)
    if len(message) > 400 and (
        _TRANSCRIPT_PATTERN.search(message) or
        (len(_TIMESTAMP_PATTERN.findall(message)) >= 3)
    ):
        return "transcript_upload"

    # 2. 캘린더 키워드
    if any(kw in message for kw in _CALENDAR_KEYWORDS):
        return "calendar_register"

    # 3. 이름 매핑 키워드
    if any(kw in msg_lower for kw in _NAME_KEYWORDS) and (
        "이야" in message or "이에요" in message or "이고" in message or "=" in message
    ):
        return "name_mapping"

    # 4. 할 일 조회
    if any(kw in msg_lower for kw in _TASK_KEYWORDS):
        return "task_query"

    # 5. 회의 검색
    if any(kw in message for kw in _SEARCH_KEYWORDS):
        return "meeting_search"

    # 6. 짧은 메시지는 LLM 분류
    if len(message) < 200:
        try:
            prompt = ROUTER_PROMPT.format(message=message[:500])
            raw = await ask_llm(prompt, max_tokens=100)
            data = json.loads(raw.strip())
            return data.get("intent", "general_chat")
        except Exception:
            pass

    return "general_chat"
