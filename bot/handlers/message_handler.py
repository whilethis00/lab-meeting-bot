"""텔레그램 메시지 핸들러: 텍스트 + 파일(.txt) 처리"""
import logging
import io
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from agents.router import classify_intent
from agents.transcript_parser import parse_transcript
from agents.speaker_mapper import (
    apply_name_mapping,
    process_name_mapping,
    smart_assign_speakers,
    get_unmapped_speakers,
)
from agents.summarizer import summarize_meeting
from agents.action_extractor import extract_actions
from agents.chat_agent import chat_response
from storage.queries import save_meeting, save_actions, get_speaker_names, get_languages, set_languages
from storage.file_storage import save_meeting_files
from utils.formatters import format_meeting_response, split_long_message

logger = logging.getLogger(__name__)

# 화자 이름 응답 대기 상태: {chat_id: {"parsed": dict, "transcript": str}}
_pending_name_input: dict[int, dict] = {}
# 언어 선택 후 분석 대기 상태: {chat_id: {"parsed": dict, "transcript": str}}
_pending_analysis: dict[int, dict] = {}

LANG_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("🇰🇷 한국어", callback_data="lang:ko"),
        InlineKeyboardButton("🇺🇸 English", callback_data="lang:en"),
    ],
    [
        InlineKeyboardButton("🇨🇳 中文", callback_data="lang:zh"),
        InlineKeyboardButton("🇯🇵 日本語", callback_data="lang:ja"),
    ],
])


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

    # 화자 이름 입력 대기 중인 경우 우선 처리
    if chat_id in _pending_name_input:
        pending = _pending_name_input.pop(chat_id)
        await update.message.reply_text("🔍 발언 내용 분석 중...")
        mapping_result = await smart_assign_speakers(chat_id, pending["parsed"], text)
        await update.message.reply_text(mapping_result, parse_mode="Markdown")

        # 화자 매핑 완료 → 언어 선택 버튼 표시
        parsed = await apply_name_mapping(pending["parsed"], chat_id)
        _pending_analysis[chat_id] = {"parsed": parsed, "transcript": pending["transcript"]}
        await update.message.reply_text(
            "🌐 요약 언어를 선택해주세요:",
            reply_markup=LANG_KEYBOARD,
        )
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
        await progress_msg.delete()

        # 2. 미매핑 화자 확인 → 있으면 이름 질문 후 대기
        existing = await get_speaker_names(chat_id)
        unmapped = get_unmapped_speakers(parsed, existing)

        if unmapped:
            _pending_name_input[chat_id] = {"parsed": parsed, "transcript": text}
            speaker_list = ", ".join(unmapped)
            await update.message.reply_text(
                f"👥 *{len(unmapped)}명의 화자*가 감지됐습니다!\n"
                f"감지된 라벨: `{speaker_list}`\n\n"
                f"참여자 이름을 알려주세요. (쉼표로 구분)\n"
                f"예: `나, 교수님, 찬우님, 성빈님`\n\n"
                f"_발언 내용을 분석해서 자동으로 매핑합니다._",
                parse_mode="Markdown",
            )
            return

        # 3. 화자 이름 치환 (기존 매핑 있는 경우)
        parsed = await apply_name_mapping(parsed, chat_id)

        # 4. 언어 선택 버튼 표시
        _pending_analysis[chat_id] = {"parsed": parsed, "transcript": text}
        await update.message.reply_text(
            "🌐 요약 언어를 선택해주세요:",
            reply_markup=LANG_KEYBOARD,
        )

    except Exception as e:
        logger.exception("전사본 처리 실패")
        await update.message.reply_text(f"❌ 분석 중 오류가 발생했습니다.\n`{e}`", parse_mode="Markdown")


async def _run_analysis(update, chat_id: int, text: str, parsed: dict, languages: list[str] | None = None):
    """파싱 완료된 데이터로 요약·저장·응답 처리. update는 Message 또는 CallbackQuery."""
    if languages is None:
        languages = await get_languages(chat_id)

    # 메시지 전송 함수 통일 (Message / CallbackQuery 모두 지원)
    async def reply(msg: str, **kwargs):
        if hasattr(update, "message") and update.message:
            return await update.message.reply_text(msg, **kwargs)
        else:
            return await update.get_bot().send_message(chat_id, msg, **kwargs)

    progress_msg = await reply("🔄 분석 중... (요약 생성)")
    try:
        import asyncio
        summary, actions = await asyncio.gather(
            summarize_meeting(parsed, languages=languages),
            extract_actions(parsed),
        )

        await progress_msg.edit_text("🔄 분석 중... (저장)")
        meeting_id = await save_meeting(chat_id, text, parsed, summary)
        await save_actions(meeting_id, actions)

        date = parsed.get("date", "unknown")
        save_meeting_files(date, text, summary, actions, parsed)

        await progress_msg.delete()

        response = format_meeting_response(summary, actions, date)
        for chunk in split_long_message(response):
            await reply(chunk, parse_mode="Markdown")

    except Exception as e:
        logger.exception("분석 실패")
        await progress_msg.edit_text(f"❌ 분석 중 오류가 발생했습니다.\n`{e}`", parse_mode="Markdown")


async def handle_lang_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """언어 선택 인라인 버튼 콜백 처리"""
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id
    lang = query.data.replace("lang:", "")

    LANG_LABELS = {"ko": "🇰🇷 한국어", "en": "🇺🇸 English", "zh": "🇨🇳 中文", "ja": "🇯🇵 日本語"}
    label = LANG_LABELS.get(lang, lang)

    # 언어 저장
    await set_languages(chat_id, [lang])
    await query.edit_message_text(f"🌐 *{label}* 로 요약합니다.", parse_mode="Markdown")

    # 대기 중인 분석 있으면 실행
    if chat_id in _pending_analysis:
        pending = _pending_analysis.pop(chat_id)
        await _run_analysis(query, chat_id, pending["transcript"], pending["parsed"], languages=[lang])
    # 대기 중인 분석 없으면 (이후 회의록에 적용됨을 안내)


async def _send_long(update: Update, text: str):
    """긴 메시지 분할 전송"""
    for chunk in split_long_message(text):
        await update.message.reply_text(chunk, parse_mode="Markdown")
