# 랩미팅 봇

클로바노트 회의록을 텔레그램으로 올리면 자동 분석·요약·저장하고, 대화형으로 조회할 수 있는 AI 에이전트.

## 기능

- 클로바노트 전사본 자동 분석 (요약 + 할 일 추출)
- "화자 1" → 실제 연구원 이름 자동 매핑
- 과거 회의 기록 자연어 검색
- 사용자 요청 시 Google Calendar 등록

## 빠른 시작

### 1. 패키지 설치

```bash
pip install -r requirements.txt
```

### 2. 환경변수 설정

```bash
cp .env.example .env
# .env 파일을 열어 아래 두 값 입력
```

```env
TELEGRAM_BOT_TOKEN=텔레그램_봇_토큰
ANTHROPIC_API_KEY=Anthropic_API_키
```

- 텔레그램 토큰: 텔레그램 앱 → `@BotFather` → `/newbot`
- Anthropic API 키: [console.anthropic.com](https://console.anthropic.com)

### 3. 실행

```bash
python -m bot.main
```

## 명령어

| 명령어 | 설명 |
|--------|------|
| `/start` | 봇 소개 |
| `/help` | 도움말 |
| `/tasks` | 미완료 할 일 목록 |
| `/meetings` | 최근 회의 목록 |
| `/setname 화자1 이름` | 화자 이름 설정 |
| `/names` | 화자 이름 매핑 확인 |
| `/done [ID]` | 할 일 완료 처리 |

## 사용법

**회의록 분석**: 클로바노트 텍스트를 그대로 붙여넣기

**화자 이름 설정**:
```
화자 1은 김연구원이고 화자 2는 박연구원이야
```

**자연어 질문**:
```
지난주 미팅에서 뭐 결정했지?
이번 달 할 일 보여줘
실험 B 건 캘린더에 넣어줘
```

## 상세 기획

[lab-meeting-bot-spec.md](./lab-meeting-bot-spec.md) 참고

## 기술 스택

- Python 3.11+
- python-telegram-bot v20+
- Claude API (Haiku / Sonnet)
- SQLite (aiosqlite) + FTS5
- Google Calendar API
