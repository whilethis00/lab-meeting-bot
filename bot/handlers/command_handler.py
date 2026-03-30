"""텔레그램 명령어 핸들러: /start, /help, /tasks, /meetings, /setname, /names, /done, /setlang, /lang"""
from telegram import Update
from telegram.ext import ContextTypes
from storage.queries import (
    get_pending_actions,
    get_recent_meetings,
    get_speaker_names,
    mark_action_done,
    get_languages,
    set_languages,
    LANG_NAMES,
)
from agents.speaker_mapper import process_name_mapping
from utils.formatters import format_task_list, format_meeting_list, split_long_message

SUPPORTED_LANGS = {"ko", "en", "zh", "cn", "ja"}


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "👋 *랩미팅 봇에 오신 것을 환영합니다!*\n\n"
        "클로바노트 전사본을 붙여넣으면 자동으로 분석해드립니다.\n\n"
        "📌 *주요 기능*\n"
        "• 회의록 자동 요약 + 할 일 추출\n"
        "• 화자 이름 자동 변환\n"
        "• 과거 회의 내용 검색\n"
        "• Google Calendar 등록\n\n"
        "/help 로 상세 사용법을 확인하세요."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 *사용법*\n\n"
        "*회의록 업로드*\n"
        "클로바노트에서 복사한 전사본을 그대로 붙여넣기\n\n"
        "*명령어*\n"
        "`/tasks` — 미완료 할 일 목록\n"
        "`/tasks all` — 전체 할 일 목록\n"
        "`/done [ID]` — 할 일 완료 처리\n"
        "`/meetings` — 최근 회의 목록\n"
        "`/setname 화자1 이름` — 화자 이름 설정\n"
        "`/names` — 현재 화자 이름 매핑 보기\n"
        "`/setlang en` — 요약 출력 언어 설정 (ko/en/zh/ja)\n"
        "`/lang` — 현재 언어 설정 확인\n\n"
        "*자연어 질문*\n"
        "\"지난주 미팅에서 뭐 결정했지?\"\n"
        "\"이번 달 할 일 보여줘\"\n"
        "\"캘린더에 넣어줘\"\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    args = context.args or []
    show_all = "all" in args

    actions = await get_pending_actions(chat_id) if not show_all else None
    if show_all:
        from storage.queries import get_all_actions
        actions = await get_all_actions(chat_id)

    text = format_task_list(actions, title="📋 전체 할 일" if show_all else "📋 미완료 할 일")
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if not args:
        await update.message.reply_text("사용법: `/done [할 일 ID]`\n예: `/done 3`", parse_mode="Markdown")
        return

    try:
        action_id = int(args[0])
        await mark_action_done(action_id)
        await update.message.reply_text(f"✅ 할 일 #{action_id}을 완료 처리했습니다.")
    except ValueError:
        await update.message.reply_text("❌ ID는 숫자여야 합니다.")


async def cmd_meetings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    meetings = await get_recent_meetings(chat_id, limit=10)
    text = format_meeting_list(meetings)
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_setname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text
    result = await process_name_mapping(chat_id, text)
    await update.message.reply_text(result, parse_mode="Markdown")


async def cmd_setlang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    args = context.args or []

    if not args:
        await update.message.reply_text(
            "📌 *요약 출력 언어 설정*\n\n"
            "사용법: `/setlang [언어코드]`\n\n"
            "지원 언어:\n"
            "• `ko` — 한국어\n"
            "• `en` — English\n"
            "• `zh` / `cn` — 中文\n"
            "• `ja` — 日本語\n\n"
            "예시:\n"
            "`/setlang ko` — 한국어로 요약\n"
            "`/setlang en` — 영어로 요약\n"
            "`/setlang zh` — 중국어로 요약",
            parse_mode="Markdown",
        )
        return

    if len(args) > 1:
        await update.message.reply_text(
            "❌ 언어는 하나만 선택할 수 있습니다.\n"
            "예: `/setlang ko`, `/setlang en`, `/setlang zh`",
            parse_mode="Markdown",
        )
        return

    lang = args[0].lower()
    if lang not in SUPPORTED_LANGS:
        await update.message.reply_text(
            f"❌ 지원하지 않는 언어 코드: `{lang}`\n"
            "지원 코드: `ko` `en` `zh` `cn` `ja`",
            parse_mode="Markdown",
        )
        return

    await set_languages(chat_id, [lang])
    label = LANG_NAMES.get(lang, lang)
    await update.message.reply_text(
        f"✅ 요약 출력 언어를 *{label}* 로 설정했습니다.\n"
        f"다음 회의록부터 적용됩니다.",
        parse_mode="Markdown",
    )


async def cmd_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    langs = await get_languages(chat_id)
    labels = [LANG_NAMES.get(l, l) for l in langs]
    await update.message.reply_text(
        f"🌐 현재 요약 출력 언어: *{' + '.join(labels)}*\n"
        f"변경: `/setlang ko en` 등",
        parse_mode="Markdown",
    )


async def cmd_names(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    names = await get_speaker_names(chat_id)
    if not names:
        await update.message.reply_text(
            "설정된 화자 이름이 없습니다.\n`/setname 화자1 이름`으로 설정하세요.",
            parse_mode="Markdown",
        )
        return

    lines = ["*현재 화자 이름 매핑*\n"]
    for label, name in names.items():
        lines.append(f"• {label} → {name}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
