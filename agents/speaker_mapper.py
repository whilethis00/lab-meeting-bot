"""Speaker Mapper: '화자 1' → 실제 이름 치환 + 이름 설정 처리"""
import json
import re
from utils.llm_client import ask_llm
from utils.prompts import SPEAKER_MAPPER_PROMPT, SMART_SPEAKER_ASSIGN_PROMPT
from storage.queries import get_speaker_names, set_speaker_name as db_set_speaker_name


async def apply_name_mapping(parsed_data: dict, chat_id: int) -> dict:
    """파싱된 데이터의 화자 라벨을 실제 이름으로 치환"""
    mappings = await get_speaker_names(chat_id)
    if not mappings:
        return parsed_data

    # segments 치환
    for segment in parsed_data.get("segments", []):
        label = segment.get("speaker", "")
        # "화자 1", "화자1" 모두 처리
        normalized = re.sub(r"\s+", " ", label).strip()
        if normalized in mappings:
            segment["speaker"] = mappings[normalized]
        elif label in mappings:
            segment["speaker"] = mappings[label]

    # participants 치환
    parsed_data["participants"] = [
        mappings.get(re.sub(r"\s+", " ", p).strip(), mappings.get(p, p))
        for p in parsed_data.get("participants", [])
    ]

    return parsed_data


def get_unmapped_speakers(parsed_data: dict, existing_mappings: dict) -> list[str]:
    """파싱 데이터에서 아직 매핑 안 된 화자 라벨 반환"""
    speakers = set()
    for seg in parsed_data.get("segments", []):
        label = re.sub(r"\s+", " ", seg.get("speaker", "")).strip()
        if label and label not in existing_mappings:
            speakers.add(label)
    return sorted(speakers)


def build_speaker_samples(parsed_data: dict, max_per_speaker: int = 3) -> dict[str, list[str]]:
    """화자별 발언 샘플 추출 (최대 N개)"""
    samples: dict[str, list[str]] = {}
    for seg in parsed_data.get("segments", []):
        label = re.sub(r"\s+", " ", seg.get("speaker", "")).strip()
        content = seg.get("content", "").strip()
        if label and content:
            if label not in samples:
                samples[label] = []
            if len(samples[label]) < max_per_speaker:
                # 너무 긴 발언은 앞 80자만
                samples[label].append(content[:80])
    return samples


async def smart_assign_speakers(
    chat_id: int, parsed_data: dict, names_input: str
) -> str:
    """발언 내용 기반으로 화자 라벨 → 실제 이름 자동 매핑"""
    # 이름 파싱 (쉼표/슬래시/공백 구분)
    names = [n.strip() for n in re.split(r"[,/\n]", names_input) if n.strip()]
    if not names:
        return "❌ 이름을 인식하지 못했습니다. 쉼표로 구분해서 다시 입력해주세요."

    existing = await get_speaker_names(chat_id)
    unmapped = get_unmapped_speakers(parsed_data, existing)

    if not unmapped:
        return "✅ 모든 화자가 이미 매핑되어 있습니다."

    samples = build_speaker_samples(parsed_data)
    speaker_samples_text = ""
    for label in unmapped:
        utterances = samples.get(label, ["(발언 없음)"])
        speaker_samples_text += f"\n[{label}]\n" + "\n".join(f"  - {u}" for u in utterances)

    prompt = SMART_SPEAKER_ASSIGN_PROMPT.format(
        speaker_samples=speaker_samples_text,
        names=", ".join(names),
    )

    try:
        raw = await ask_llm(prompt, max_tokens=800)
        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
        mappings = json.loads(raw)
    except Exception:
        return "❌ 자동 매핑 실패. `/setname 화자1 이름` 으로 수동 설정해주세요."

    saved = []
    for m in mappings:
        label = re.sub(r"\s+", " ", m.get("label", "")).strip()
        name = m.get("name", "").strip()
        reason = m.get("reason", "")
        if label and name and label in unmapped:
            await db_set_speaker_name(chat_id, label, name)
            saved.append(f"• {label} → **{name}** _{reason}_")

    if not saved:
        return "❌ 매핑할 수 없었습니다. 수동으로 `/setname` 을 사용해주세요."

    return "✅ 화자 이름을 자동 매핑했습니다!\n" + "\n".join(saved)


async def process_name_mapping(chat_id: int, message: str) -> str:
    """사용자 메시지에서 화자 이름 매핑 추출 후 저장"""
    # /setname 명령어 처리
    setname_match = re.match(r"/setname\s+(화자\s*\d+)\s+(.+)", message.strip(), re.IGNORECASE)
    if setname_match:
        label = re.sub(r"\s+", " ", setname_match.group(1)).strip()
        name = setname_match.group(2).strip()
        await db_set_speaker_name(chat_id, label, name)
        return f"✅ 이름을 설정했습니다.\n• {label} → {name}\n이후 회의록에서 자동으로 변환됩니다."

    # LLM으로 자연어 파싱
    try:
        prompt = SPEAKER_MAPPER_PROMPT.format(message=message)
        raw = await ask_llm(prompt, max_tokens=500)
        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
        mappings = json.loads(raw)
    except Exception:
        return "❌ 이름 설정 형식을 이해하지 못했습니다.\n예시: `화자 1은 김연구원이고 화자 2는 박연구원이야`"

    if not mappings:
        return "❌ 이름 매핑을 찾을 수 없습니다."

    saved = []
    for m in mappings:
        label = re.sub(r"\s+", " ", m.get("label", "")).strip()
        name = m.get("name", "").strip()
        if label and name:
            await db_set_speaker_name(chat_id, label, name)
            saved.append(f"• {label} → {name}")

    if not saved:
        return "❌ 저장할 이름 매핑이 없습니다."

    result = "✅ 화자 이름을 설정했습니다.\n" + "\n".join(saved)
    result += "\n\n이후 회의록에서 자동으로 변환됩니다."
    return result
