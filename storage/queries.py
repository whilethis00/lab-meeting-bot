"""SQLite CRUD 쿼리"""
import json
import aiosqlite
from storage.database import get_db_path


async def save_meeting(
    chat_id: int,
    raw_transcript: str,
    parsed_data: dict,
    summary: str,
    decisions: list = None,
    open_issues: list = None,
) -> int:
    date = parsed_data.get("date", "")
    title = f"{date} 랩미팅"

    async with aiosqlite.connect(get_db_path()) as db:
        cursor = await db.execute(
            """INSERT INTO meetings
               (date, title, raw_transcript, parsed_data, summary, decisions, open_issues, telegram_chat_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                date,
                title,
                raw_transcript,
                json.dumps(parsed_data, ensure_ascii=False),
                summary,
                json.dumps(decisions or [], ensure_ascii=False),
                json.dumps(open_issues or [], ensure_ascii=False),
                chat_id,
            ),
        )
        await db.commit()
        return cursor.lastrowid


async def save_actions(meeting_id: int, actions: list):
    async with aiosqlite.connect(get_db_path()) as db:
        for a in actions:
            await db.execute(
                """INSERT INTO action_items (meeting_id, description, assignee, deadline, priority)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    meeting_id,
                    a.get("description", ""),
                    a.get("assignee"),
                    a.get("deadline"),
                    a.get("priority", "medium"),
                ),
            )
        await db.commit()


async def get_pending_actions(chat_id: int) -> list[dict]:
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT ai.* FROM action_items ai
               JOIN meetings m ON ai.meeting_id = m.id
               WHERE m.telegram_chat_id = ? AND ai.status = 'pending'
               ORDER BY ai.priority DESC, ai.deadline ASC""",
            (chat_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_all_actions(chat_id: int) -> list[dict]:
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT ai.* FROM action_items ai
               JOIN meetings m ON ai.meeting_id = m.id
               WHERE m.telegram_chat_id = ?
               ORDER BY ai.created_at DESC""",
            (chat_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def mark_action_done(action_id: int):
    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute(
            """UPDATE action_items SET status='done', completed_at=datetime('now')
               WHERE id=?""",
            (action_id,),
        )
        await db.commit()


async def get_recent_meetings(chat_id: int, limit: int = 10) -> list[dict]:
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT id, date, title, summary FROM meetings
               WHERE telegram_chat_id = ?
               ORDER BY date DESC, created_at DESC LIMIT ?""",
            (chat_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def search_meetings(chat_id: int, keyword: str) -> list[dict]:
    """FTS5 전문 검색"""
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        try:
            cursor = await db.execute(
                """SELECT m.id, m.date, m.title, m.summary
                   FROM meetings_fts fts
                   JOIN meetings m ON fts.rowid = m.id
                   WHERE meetings_fts MATCH ? AND m.telegram_chat_id = ?
                   ORDER BY m.date DESC LIMIT 5""",
                (keyword, chat_id),
            )
        except Exception:
            # FTS 실패 시 LIKE 폴백
            cursor = await db.execute(
                """SELECT id, date, title, summary FROM meetings
                   WHERE telegram_chat_id = ? AND (summary LIKE ? OR title LIKE ?)
                   ORDER BY date DESC LIMIT 5""",
                (chat_id, f"%{keyword}%", f"%{keyword}%"),
            )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_meeting_context(chat_id: int, keyword: str = "", limit: int = 3) -> str:
    """Chat Agent 용 컨텍스트 문자열 반환"""
    if keyword:
        meetings = await search_meetings(chat_id, keyword)
    else:
        meetings = await get_recent_meetings(chat_id, limit)

    if not meetings:
        return "저장된 회의 기록이 없습니다."

    context_parts = []
    for m in meetings:
        context_parts.append(f"=== {m['date']} 회의 ===\n{m['summary'] or '요약 없음'}")

    return "\n\n".join(context_parts)


async def save_chat_context(chat_id: int, role: str, content: str):
    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute(
            "INSERT INTO chat_context (chat_id, role, content) VALUES (?, ?, ?)",
            (chat_id, role, content),
        )
        # 최근 20개만 유지
        await db.execute(
            """DELETE FROM chat_context WHERE chat_id=? AND id NOT IN (
               SELECT id FROM chat_context WHERE chat_id=? ORDER BY id DESC LIMIT 20)""",
            (chat_id, chat_id),
        )
        await db.commit()


async def get_chat_history(chat_id: int, limit: int = 6) -> list[dict]:
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT role, content FROM chat_context
               WHERE chat_id=? ORDER BY id DESC LIMIT ?""",
            (chat_id, limit),
        )
        rows = await cursor.fetchall()
        return list(reversed([dict(r) for r in rows]))


# 화자 이름 매핑
async def set_speaker_name(chat_id: int, label: str, name: str):
    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute(
            """INSERT INTO speaker_names (chat_id, clova_label, real_name)
               VALUES (?, ?, ?)
               ON CONFLICT(chat_id, clova_label) DO UPDATE SET
               real_name=excluded.real_name,
               updated_at=datetime('now')""",
            (chat_id, label, name),
        )
        await db.commit()


LANG_NAMES = {
    "ko": "한국어",
    "en": "English",
    "zh": "中文",
    "cn": "中文",
    "ja": "日本語",
}


async def get_languages(chat_id: int) -> list[str]:
    """채팅별 출력 언어 설정 반환 (기본: ['ko'])"""
    async with aiosqlite.connect(get_db_path()) as db:
        cursor = await db.execute(
            "SELECT languages FROM chat_settings WHERE chat_id=?", (chat_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return ["ko"]
        return [lang.strip() for lang in row[0].split(",") if lang.strip()]


async def set_languages(chat_id: int, languages: list[str]) -> None:
    """채팅별 출력 언어 설정 저장"""
    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute(
            """INSERT INTO chat_settings (chat_id, languages)
               VALUES (?, ?)
               ON CONFLICT(chat_id) DO UPDATE SET
               languages=excluded.languages,
               updated_at=datetime('now')""",
            (chat_id, ",".join(languages)),
        )
        await db.commit()


async def get_speaker_names(chat_id: int) -> dict:
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT clova_label, real_name FROM speaker_names WHERE chat_id=?",
            (chat_id,),
        )
        rows = await cursor.fetchall()
        return {r["clova_label"]: r["real_name"] for r in rows}
