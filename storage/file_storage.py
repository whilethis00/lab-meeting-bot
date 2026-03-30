"""날짜별 파일 저장 — Desktop/claude/labmeeting/{date}/"""
import os
import json
from datetime import datetime
from bot.config import LABMEETING_PATH


def _meeting_dir(date: str) -> str:
    return os.path.join(LABMEETING_PATH, date)


def save_meeting_files(
    date: str,
    raw_transcript: str,
    summary: str,
    actions: list,
    parsed_data: dict = None,
):
    """회의 날짜 폴더에 원본/요약/할일 파일 저장"""
    dir_path = _meeting_dir(date)
    os.makedirs(dir_path, exist_ok=True)

    # 원본 전사본
    with open(os.path.join(dir_path, "raw_transcript.txt"), "w", encoding="utf-8") as f:
        f.write(raw_transcript)

    # 요약 마크다운
    summary_content = f"# {date} 랩미팅 요약\n\n{summary}\n"
    with open(os.path.join(dir_path, "summary.md"), "w", encoding="utf-8") as f:
        f.write(summary_content)

    # 할 일 JSON
    with open(os.path.join(dir_path, "action_items.json"), "w", encoding="utf-8") as f:
        json.dump(actions, f, ensure_ascii=False, indent=2)

    # 파싱된 데이터 (선택)
    if parsed_data:
        with open(os.path.join(dir_path, "parsed_data.json"), "w", encoding="utf-8") as f:
            json.dump(parsed_data, f, ensure_ascii=False, indent=2)

    return dir_path


def list_meeting_dates() -> list[str]:
    """저장된 회의 날짜 목록 반환"""
    if not os.path.exists(LABMEETING_PATH):
        return []
    dates = []
    for name in sorted(os.listdir(LABMEETING_PATH), reverse=True):
        if os.path.isdir(os.path.join(LABMEETING_PATH, name)):
            dates.append(name)
    return dates


def read_summary(date: str) -> str | None:
    path = os.path.join(_meeting_dir(date), "summary.md")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    return None
