# 랩미팅 봇

클로바노트/다글로 회의록을 텔레그램으로 올리면 자동 분석·요약·저장하고, 대화형으로 조회할 수 있는 AI 에이전트.

## 주요 기능

- **다글로 / 클로바노트** 전사본 자동 인식 및 파싱
- **스마트 화자 매핑** — 발언 내용을 분석해 "Speaker 1" → "교수님" 자동 추론 (Claude Haiku)
- **다국어 요약** — 한국어 / 영어 / 중국어 / 일본어 선택 출력 (Claude Sonnet)
- **액션 아이템 자동 추출** — 담당자·기한·우선순위 포함
- 과거 회의 기록 자연어 검색 및 질의응답
- Google Calendar 등록 (선택)

## 업로드 흐름

```
파일 업로드 (.txt)
  ↓
화자 감지 → "참여자 이름을 알려주세요"
  ↓
LLM이 발언 패턴 분석 → 자동 이름 매핑
  ↓
언어 선택 버튼 (🇰🇷 🇺🇸 🇨🇳 🇯🇵)
  ↓
요약 + 할 일 목록 출력
```

## 지원 전사 앱

| 앱 | 포맷 |
|----|------|
| 클로바노트 | `화자 N HH:MM:SS\n내용` |
| 다글로 | `MM:SS Speaker N\n내용` |

## 빠른 시작

### 1. 패키지 설치

```bash
pip install -r requirements.txt
```

### 2. 환경변수 설정

```bash
cp .env.example .env
```

```env
TELEGRAM_BOT_TOKEN=텔레그램_봇_토큰
ANTHROPIC_API_KEY=Anthropic_API_키
```

- 텔레그램 토큰: `@BotFather` → `/newbot`
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
| `/tasks all` | 전체 할 일 목록 |
| `/meetings` | 최근 회의 목록 |
| `/done [ID]` | 할 일 완료 처리 |
| `/setname 화자1 이름` | 화자 이름 수동 설정 |
| `/names` | 화자 이름 매핑 확인 |
| `/setlang ko` | 요약 언어 설정 (ko/en/zh/ja) |
| `/lang` | 현재 언어 설정 확인 |

## 사용법

**회의록 분석**: 클로바노트 또는 다글로 `.txt` 파일을 첨부하거나 텍스트 직접 붙여넣기

**자연어 질문**:
```
지난주 미팅에서 뭐 결정했지?
이번 달 할 일 보여줘
실험 B 건 캘린더에 넣어줘
교수님이 자주 지적하시는 게 뭐야?
```

## 기술 스택

| 구분 | 내용 |
|------|------|
| 언어 | Python 3.11+ |
| 텔레그램 | python-telegram-bot v20+ |
| LLM | Claude Haiku (파싱·라우팅·화자매핑) / Sonnet (요약·대화) |
| DB | SQLite (aiosqlite) + FTS5 |
| 캘린더 | Google Calendar API |

## 상세 기획 및 개발 계획

[develop.md](./develop.md) 참고
