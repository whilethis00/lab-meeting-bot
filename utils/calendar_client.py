"""Google Calendar API 래퍼"""
import os
import asyncio
from datetime import datetime, timedelta
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from bot.config import GOOGLE_CALENDAR_CREDENTIALS

SCOPES = ["https://www.googleapis.com/auth/calendar"]
TOKEN_PATH = "./data/token.json"


def _get_credentials() -> Credentials:
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                GOOGLE_CALENDAR_CREDENTIALS, SCOPES
            )
            creds = flow.run_local_server(port=0)
        os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())

    return creds


def _create_event_sync(title: str, date: str, description: str = "") -> dict:
    creds = _get_credentials()
    service = build("calendar", "v3", credentials=creds)

    event = {
        "summary": title,
        "description": description,
        "start": {"date": date},
        "end": {"date": date},
    }

    result = service.events().insert(calendarId="primary", body=event).execute()
    return result


async def create_calendar_event(
    title: str, date: str, description: str = ""
) -> str:
    """Google Calendar에 이벤트 생성 (날짜 단위)"""
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, _create_event_sync, title, date, description
        )
        return result.get("htmlLink", "등록 완료")
    except Exception as e:
        raise RuntimeError(f"캘린더 등록 실패: {e}")


async def is_calendar_available() -> bool:
    """캘린더 API 사용 가능 여부 확인"""
    try:
        loop = asyncio.get_event_loop()
        creds = await loop.run_in_executor(None, _get_credentials)
        return creds is not None and creds.valid
    except Exception:
        return False
