"""텔레그램 메시지 핸들러: 텍스트 + 파일(.txt) 처리"""
import logging
import io
from telegram import Update
from telegram.ext import ContextTypes

from agents.router import classify_intent
from agents.transcript_parser import parse_transcript
from agents.speaker_mapper import apply_name_mapping, process_name_mapping
from agents.summarizer import summarize_meeting
from agents.action_extractor import extract_actions
from agents.chat_agent import chat_response
from storage.queries import save_meeting, save_actions
from storage.file_storage import save_meeting_files
from utils.formatters import format_meeting_response, split_long_message

logger = logging.getLogger(__name__)


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """파일 업로드 처리 (.txt, .md 등 텍스트 파일)"""
    doc = update.message.document
    chat_id = update.effective_chat.id

    if not doc:
        return

    # 텍스트 파일만 허용
    allowed_mimes = {"text/plain", "text/markdown", "application/octet-stream"}
    allowed_exts = {".txt", ".md", ".text"}
    filename = doc.file_name or ""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if doc.mime_type not in allowed_mimes and ext not in allowed_exts:
        await update.message.reply_text(
            f"❌ `.txt` 파일만 지원합니다. (받은 파일: `{filename}`)",
            parse_mode="Markdown",
        )
        return

    await update.message.reply_text(f"📂 `{filename}` 파일 읽는 중...", parse_mode="Markdown")

    try:
        file = await doc.get_file()
        buf = io.BytesIO()
        await file.download_to_memory(buf)
        text = buf.getvalue().decode("utf-8", errors="replace")
    except Exception as e:
        await update.message.reply_text(f"❌ 파일 읽기 실패: `{e}`", parse_mode="Markdown")
        return

    if len(text.strip()) < 50:
        await update.message.reply_text("❌ 파일 내용이 너무 짧습니다.", parse_mode="Markdown")
        return

    await _handle_transcript(update, chat_id, text)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.effective_chat.id

    if not text:
        return

    intent = await classify_intent(text)
    logger.info(f"[chat={chat_id}] intent={intent}, len={len(text)}")

    if intent == "transcript_upload":
        await _handle_transcript(update, chat_id, text)

    elif intent == "name_mapping":
        result = await process_name_mapping(chat_id, text)
        await update.message.reply_text(result, parse_mode="Markdown")

    elif intent == "calendar_register":
        await update.message.reply_text("📅 캘린더 등록 처리 중...")
        reply = await chat_response(chat_id, text, mode="calendar")
        await _send_long(update, reply)

    elif intent == "task_query":
        reply = await chat_response(chat_id, text, mode="task")
        await _send_long(update, reply)

    else:
        # meeting_search, general_chat 모두 Chat Agent로
        reply = await chat_response(chat_id, text, mode="general")
        await _send_long(update, reply)


async def _handle_transcript(update: Update, chat_id: int, text: str):
    """전사본 처리 파이프라인"""
    progress_msg = await update.message.reply_text("🔄 회의록 분석 중... (1/4 파싱)")

    try:
        # 1. 파싱
        parsed = await parse_transcript(text)

        await progress_msg.edit_text("🔄 분석 중... (2/4 화자 이름 변환)")
        # 2. 화자 이름 치환
        parsed = await apply_name_mapping(parsed, chat_id)

        await progress_msg.edit_text("🔄 분석 중... (3/4 요약 생성)")
        # 3. 요약 + 액션 아이템 병렬 처리
        import asyncio
        summary, actions = await asyncio.gather(
            summarize_meeting(parsed),
            extract_actions(parsed),
        )

        await progress_msg.edit_text("🔄 분석 중... (4/4 저장)")
        # 4. DB 저장
        meeting_id = await save_meeting(chat_id, text, parsed, summary)
        await save_actions(meeting_id, actions)

        # 5. 파일 저장
        date = parsed.get("date", "unknown")
        save_meeting_files(date, text, summary, actions, parsed)

        await progress_msg.delete()

        # 6. 응답 전송
        response = format_meeting_response(summary, actions, date)
        for chunk in split_long_message(response):
            await update.message.reply_text(chunk, parse_mode="Markdown")

    except Exception as e:
        logger.exception("전사본 처리 실패")
        await progress_msg.edit_text(f"❌ 분석 중 오류가 발생했습니다.\n`{e}`", parse_mode="Markdown")


async def _send_long(update: Update, text: str):
    """긴 메시지 분할 전송"""
    for chunk in split_long_message(text):
        await update.message.reply_text(chunk, parse_mode="Markdown")
