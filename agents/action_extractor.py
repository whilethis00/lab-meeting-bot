"""Action Item Extractor: 회의 내용 → 할 일 목록 추출"""
import json
import re
from utils.llm_client import ask_llm
from utils.prompts import ACTION_EXTRACTOR_PROMPT


async def extract_actions(parsed_data: dict) -> list[dict]:
    """Haiku로 액션 아이템 추출"""
    prompt = ACTION_EXTRACTOR_PROMPT.format(
        parsed_data=json.dumps(parsed_data, ensure_ascii=False, indent=2)[:3500]
    )

    try:
        raw = await ask_llm(prompt, max_tokens=1500)
        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()

        # JSON 배열 추출
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            raw = match.group(0)

        actions = json.loads(raw)
        return _validate_actions(actions)
    except Exception:
        return []


def _validate_actions(actions: list) -> list[dict]:
    validated = []
    for a in actions:
        if not isinstance(a, dict):
            continue
        validated.append({
            "description": str(a.get("description", "")).strip(),
            "assignee": a.get("assignee") or None,
            "deadline": a.get("deadline") or None,
            "priority": a.get("priority", "medium") if a.get("priority") in ("high", "medium", "low") else "medium",
        })
    return [a for a in validated if a["description"]]
