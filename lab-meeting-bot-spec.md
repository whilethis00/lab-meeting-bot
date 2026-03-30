# Lab Meeting Bot — MVP 기획서

> 클로바노트 회의록을 텔레그램으로 올리면 자동 분석·정리·저장하고, 대화형으로 조회할 수 있는 AI 에이전트.
> 캘린더 등록은 텔레그램에서 명시적으로 요청할 때만 동작.

---

## 개념도

```
[클로바노트] → (텍스트 복사/공유) → [텔레그램 봇]
                                        │
                                   [Router Agent]
                              ┌─────┬────┴────┬──────────┐
                         회의록 업로드  대화/질의  화자설정  캘린더등록
                              │         │        │          │
                      [Processing Pipeline]│  [Speaker   [Calendar
                       ├─ Parser        │   Mapper]    Register]
                       ├─ Speaker Map   │               │
                       ├─ Summarizer    │        [Google Calendar]
                       └─ Action Extract│
                              │         │
                        [SQLite DB] ←───┤
                              │         │
                      [Response Formatter]
                              │
                        [텔레그램 응답]
                   (요약 + 실명 할일 + 대화 + 📅캘린더)
```

---

## 1. 프로젝트 개요

### 1.1 목적
- 랩미팅 후 클로바노트 기록을 텔레그램에 전달하면 자동으로 분석·요약
- 날짜별 회의 기록 저장 및 조회
- 액션아이템(할 일) 자동 추출 및 관리
- "화자 1" → 실제 연구원 이름 자동 매핑
- 텔레그램 대화를 통한 과거 회의 검색 및 질의응답
- 사용자 요청 시 할일을 Google Calendar에 등록

### 1.2 사용 시나리오
1. 사용자가 랩미팅 후 클로바노트 앱에서 회의록 텍스트를 복사
2. 텔레그램 봇 채팅방에 텍스트를 붙여넣기 (또는 파일 전송)
3. 봇이 자동으로 분석하여 요약본 + 할일 목록 응답 (실제 이름으로 표시)
4. 이후 "지난주 미팅에서 뭐 결정했지?", "이번 달 할일 보여줘" 등 대화 가능
5. "실험 B 건 캘린더에 넣어줘" 등 요청하면 Google Calendar에 등록

### 1.3 기술 스택 (MVP)

| 구분 | 선택 | 이유 |
|------|------|------|
| 언어 | Python 3.11+ | 빠른 프로토타이핑, LLM 라이브러리 풍부 |
| 텔레그램 | python-telegram-bot v20+ | async 지원, 안정적 |
| LLM | Claude API (Haiku/Sonnet) | 한국어 성능, 구조화 출력 우수 |
| DB | SQLite (aiosqlite) | 설치 불필요, MVP에 적합 |
| 캘린더 | Google Calendar API | 사용자 요청 시 할일 등록 |
| 배포 | 로컬 PC → 연구실 PC → (필요시) Railway/Fly.io | 단계적 확장 |

---

## 2. 시스템 아키텍처

### 2.1 디렉토리 구조

```
lab-meeting-bot/
├── bot/
│   ├── __init__.py
│   ├── main.py              # 엔트리포인트, 텔레그램 봇 실행
│   ├── config.py             # 환경변수, 설정
│   └── handlers/
│       ├── __init__.py
│       ├── message_handler.py  # 텔레그램 메시지 수신 처리
│       └── command_handler.py  # /start, /help, /tasks 등 명령어
├── agents/
│   ├── __init__.py
│   ├── router.py             # Router Agent: 메시지 의도 분류
│   ├── transcript_parser.py  # 클로바노트 텍스트 파싱
│   ├── speaker_mapper.py     # 화자 이름 매핑 ("화자 1" → "김연구원")
│   ├── summarizer.py         # 회의 요약 생성
│   ├── action_extractor.py   # 액션아이템 추출
│   └── chat_agent.py         # 대화형 질의응답 (RAG) + 캘린더 등록
├── storage/
│   ├── __init__.py
│   ├── database.py           # SQLite 연결, 초기화
│   └── queries.py            # CRUD 쿼리
├── utils/
│   ├── __init__.py
│   ├── llm_client.py         # Claude API 래퍼
│   ├── formatters.py         # 텔레그램 마크다운 포맷터
│   ├── calendar_client.py    # Google Calendar API 래퍼
│   └── prompts.py            # 프롬프트 템플릿 모음
├── credentials.json          # Google OAuth 인증 (git 제외)
├── token.json                # Google OAuth 토큰 (자동 생성, git 제외)
├── .env                      # TELEGRAM_BOT_TOKEN, ANTHROPIC_API_KEY
├── .gitignore
├── requirements.txt
└── README.md
```

### 2.2 데이터베이스 스키마

```sql
-- 회의록 테이블
CREATE TABLE meetings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,                    -- 회의 날짜 (YYYY-MM-DD)
    title TEXT,                            -- 자동 생성 제목
    raw_transcript TEXT NOT NULL,          -- 클로바노트 원본
    parsed_data TEXT,                      -- 구조화된 JSON
    summary TEXT,                          -- 요약문
    decisions TEXT,                        -- 결정사항 JSON
    open_issues TEXT,                      -- 미결이슈 JSON
    created_at TEXT DEFAULT (datetime('now')),
    telegram_chat_id INTEGER              -- 텔레그램 채팅 ID
);

-- 액션아이템 테이블
CREATE TABLE action_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id INTEGER REFERENCES meetings(id),
    description TEXT NOT NULL,             -- 할 일 내용
    assignee TEXT,                         -- 담당자 (실제 이름)
    deadline TEXT,                         -- 기한
    priority TEXT DEFAULT 'medium',        -- high/medium/low
    status TEXT DEFAULT 'pending',         -- pending/in_progress/done
    created_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT
);

-- 화자 이름 매핑 테이블
CREATE TABLE speaker_names (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,              -- 텔레그램 채팅 ID
    clova_label TEXT NOT NULL,             -- 클로바노트 라벨 ("화자 1")
    real_name TEXT NOT NULL,               -- 실제 이름 ("김연구원")
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(chat_id, clova_label)
);

-- 대화 컨텍스트
CREATE TABLE chat_context (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    role TEXT NOT NULL,                    -- user/assistant
    content TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);
```

---

## 3. 서브에이전트 상세 설계

### 3.1 Router Agent

**역할**: 텔레그램으로 들어온 메시지의 의도를 분류하여 적절한 에이전트로 라우팅

**분류 기준**:

| 유형 | 판별 조건 | 라우팅 대상 |
|------|-----------|-------------|
| 회의록 업로드 | 긴 텍스트(500자+), 화자 패턴, 시간 패턴 포함 | → Processing Pipeline |
| 할일 조회 | "할일", "태스크", "할 일", "/tasks" 등 | → Chat Agent (task mode) |
| 회의 검색 | "지난", "이전", "회의", "미팅" 등 | → Chat Agent (search mode) |
| 캘린더 등록 | "캘린더에 넣어줘", "일정 등록" 등 | → Chat Agent (calendar mode) |
| 화자 이름 설정 | "화자 1은 김연구원이야", /setname 등 | → Speaker Mapper |
| 일반 대화 | 위에 해당 없음 | → Chat Agent (general) |
| 명령어 | /start, /help, /tasks, /meetings, /setname, /names | → Command Handler |

**구현 방식**: LLM 분류 (짧은 프롬프트로 intent 판별) + 규칙 기반 하이브리드

```python
# agents/router.py 핵심 로직
ROUTER_PROMPT = """
다음 메시지의 의도를 분류하세요.
카테고리: transcript_upload | task_query | meeting_search | calendar_register | name_mapping | general_chat

메시지가 500자 이상이고 회의록/대화 형태이면 transcript_upload입니다.
"캘린더", "일정 등록", "캘린더에 넣어" 등이면 calendar_register입니다.
"화자 1은 ~", "이름 설정" 등이면 name_mapping입니다.

메시지: {message}

JSON으로만 응답: {{"intent": "카테고리", "confidence": 0.0-1.0}}
"""
```

### 3.2 Transcript Parser

**역할**: 클로바노트 텍스트를 구조화된 데이터로 변환

**입력 예시** (클로바노트 포맷):
```
화자 1 00:00:12
오늘 진행상황 공유하겠습니다. 지난주에 말씀드린 실험 결과가 나왔는데요.

화자 2 00:01:34
네, 저도 데이터 분석 결과를 가져왔습니다.
```

**출력 JSON**:
```json
{
  "date": "2026-03-19",
  "participants": ["화자 1", "화자 2"],
  "segments": [
    {
      "speaker": "화자 1",
      "timestamp": "00:00:12",
      "content": "오늘 진행상황 공유하겠습니다...",
      "topic": "진행상황 공유"
    }
  ],
  "duration_minutes": 45,
  "topic_sections": [
    {"topic": "실험 결과 공유", "start": "00:00:12", "end": "00:15:30"},
    {"topic": "데이터 분석", "start": "00:15:30", "end": "00:30:00"}
  ]
}
```

**프롬프트 전략**: 클로바노트 특유의 포맷(화자 + 타임스탬프 + 내용)을 인식하여 파싱. 화자 이름이 "화자 1" 같은 기본값이면 내용에서 실제 이름 추론 시도.

### 3.3 Speaker Mapper (화자 이름 매핑)

**역할**: 클로바노트의 "화자 1", "화자 2" 등을 실제 연구원 이름으로 변환

**동작 방식**:
1. 사용자가 `/setname 화자1 김연구원` 또는 대화로 "화자 1은 김연구원이야" 입력
2. `speaker_names` 테이블에 매핑 저장
3. 이후 회의록 파싱 시 자동으로 치환

**사용 예시**:
```
사용자: 화자 1은 김연구원이고, 화자 2는 박연구원이야
봇: ✅ 화자 이름을 설정했습니다.
  • 화자 1 → 김연구원
  • 화자 2 → 박연구원
  앞으로 회의록에서 자동으로 변환됩니다.
```

**파싱 파이프라인 적용**: Transcript Parser 출력에서 speaker 필드를 speaker_names 테이블과 대조하여 치환. 매핑이 없는 화자는 원래 라벨 유지.

```python
# agents/speaker_mapper.py 핵심 로직
async def apply_name_mapping(parsed_data: dict, chat_id: int) -> dict:
    """파싱된 데이터의 화자 라벨을 실제 이름으로 치환"""
    mappings = await get_speaker_names(chat_id)  # DB에서 매핑 조회
    for segment in parsed_data["segments"]:
        label = segment["speaker"]
        if label in mappings:
            segment["speaker"] = mappings[label]
    parsed_data["participants"] = [
        mappings.get(p, p) for p in parsed_data["participants"]
    ]
    return parsed_data
```

### 3.4 Meeting Summarizer

**역할**: 파싱된 데이터를 기반으로 구조화된 회의 요약 생성

**출력 포맷**:
```markdown
## 📋 회의 요약 — 2026.03.19

### 핵심 논의사항
1. 실험 A 결과: 유의미한 차이 확인 (p < 0.05)
2. 데이터 전처리 파이프라인 개선 필요

### 결정사항
- 실험 B를 다음 주까지 추가 진행
- 분석 코드 리팩토링 우선

### 미결 이슈
- 시약 수급 일정 미확정
- IRB 승인 대기 중
```

### 3.5 Action Item Extractor

**역할**: 회의 내용에서 할 일을 자동 추출

**추출 대상**:
- 명시적 할당: "A가 ~하기로 했다", "~까지 ~해주세요"
- 암묵적 할당: "~가 필요하다" → 관련 화자에게 배정
- 기한 포함: "다음 주까지", "금요일까지"

**출력 예시** (화자 이름 매핑 적용 후):
```json
[
  {
    "description": "실험 B 추가 진행",
    "assignee": "김연구원",
    "deadline": "2026-03-26",
    "priority": "high"
  },
  {
    "description": "분석 코드 리팩토링",
    "assignee": "박연구원",
    "deadline": null,
    "priority": "medium"
  }
]
```

### 3.6 Chat Agent (RAG + 캘린더)

**역할**: 사용자와 자연어 대화, 과거 회의 기록 기반 질의응답, 캘린더 등록

**동작 방식**:
1. 사용자 질문 수신
2. DB에서 관련 회의록 검색 (키워드 + 날짜 기반)
3. 검색 결과를 LLM 컨텍스트에 주입
4. LLM이 답변 생성

**지원 질의 예시**:
- "지난주 미팅에서 김연구원이 맡기로 한 거 뭐였지?"
- "3월 할일 목록 보여줘"
- "실험 B 진행상황 관련 논의 찾아줘"
- "이번 달 미결 이슈 정리해줘"
- "실험 B 추가 진행 캘린더에 넣어줘" → Google Calendar API로 이벤트 생성

**캘린더 등록 모드**: 사용자가 텔레그램에서 명시적으로 요청할 때만 동작. 자동 등록 없음.
- 할일 지정: "실험 B 건 캘린더에 3/26으로 넣어줘"
- 전체 등록: "오늘 할일 다 캘린더에 넣어줘"
- Google Calendar API 호출하여 이벤트 생성 후 확인 메시지 응답

**검색 전략 (MVP)**:
- SQLite FTS5 (Full-Text Search) 사용
- 날짜 필터 + 키워드 매칭
- 향후 임베딩 기반 시맨틱 검색으로 업그레이드 가능

---

## 4. 텔레그램 봇 인터페이스

### 4.1 명령어

| 명령어 | 설명 |
|--------|------|
| `/start` | 봇 소개 및 사용법 안내 |
| `/help` | 도움말 표시 |
| `/tasks` | 미완료 할일 목록 조회 |
| `/tasks done` | 완료 처리 (인라인 버튼) |
| `/meetings` | 최근 회의 목록 (최근 10개) |
| `/search 키워드` | 회의록 검색 |
| `/setname 화자1 이름` | 화자 이름 매핑 설정 |
| `/names` | 현재 화자 이름 매핑 목록 조회 |

### 4.2 메시지 처리 흐름

**회의록 업로드 시 응답 예시**:
```
✅ 회의록 분석 완료!

📋 2026.03.19 랩미팅

📌 핵심 요약
1. 실험 A 결과 유의미 (p<0.05)
2. 데이터 파이프라인 개선 필요

🎯 결정사항
• 실험 B 다음 주까지 추가 진행
• 분석 코드 리팩토링 우선

📝 할 일 (3건)
1. [HIGH] 실험 B 추가 진행 — 김연구원 (3/26까지)
2. [MED] 분석 코드 리팩토링 — 박연구원
3. [MED] 시약 발주 확인 — 김연구원

💬 질문이 있으면 편하게 물어보세요!
📅 캘린더에 등록하려면 "캘린더에 넣어줘"라고 말씀해주세요.
```

**대화 응답 예시**:
```
사용자: 지난주에 시약 관련해서 뭐라고 했지?

봇: 3/12 미팅에서 시약 관련 논의가 있었습니다.
- 김연구원이 시약 A 수급이 2주 지연될 수 있다고 보고
- 대안으로 시약 B 사용 가능성 검토하기로 결정
- 박연구원이 시약 B 호환성 테스트 진행하기로 함

관련 할일: "시약 B 호환성 테스트" (박연구원, 진행중)
```

**캘린더 등록 예시**:
```
사용자: 실험 B 추가 진행 캘린더에 넣어줘

봇: ✅ Google Calendar에 등록했습니다.
📅 실험 B 추가 진행
   담당: 김연구원
   날짜: 2026-03-26
   출처: 3/19 랩미팅
```

### 4.3 인라인 버튼

회의록 분석 결과와 함께 인라인 버튼 제공:
- `[📋 전체 보기]` — 상세 회의록 표시
- `[✅ 할일 완료]` — 할일 상태 변경
- `[🔍 관련 회의]` — 비슷한 주제 회의 검색
- `[📅 캘린더 등록]` — 기한 있는 할일을 Google Calendar에 등록

---

## 5. MVP 개발 단계

### Phase 1: 기본 골격 (Day 1-2)
**목표**: 텔레그램 봇이 메시지를 받고 Echo 응답

- [x] 프로젝트 구조 생성
- [x] 기본 메시지 핸들러 구현
- [x] SQLite 데이터베이스 초기화
- [x] Claude API 연결 (llm_client 래퍼)
- [x] 환경변수 설정 (.env.example)
- [ ] 텔레그램 봇 토큰 발급 및 연결

**완료 기준**: 텔레그램에서 메시지 보내면 봇이 응답

### Phase 2: 회의록 처리 파이프라인 (Day 3-4)
**목표**: 클로바노트 텍스트를 분석하여 요약 + 할일 추출

- [x] Router Agent 구현 (의도 분류)
- [x] Transcript Parser 구현 (클로바노트 포맷 파싱)
- [x] Speaker Mapper 구현 (화자 이름 매핑 + /setname, /names)
- [x] Meeting Summarizer 구현 (요약 생성)
- [x] Action Extractor 구현 (할일 추출)
- [x] DB에 회의록 + 할일 저장
- [x] 텔레그램 응답 포맷터 구현

**완료 기준**: 클로바노트 텍스트 전송 시 요약 + 할일이 실제 이름으로 응답

### Phase 3: 대화 + 캘린더 기능 (Day 5-6)
**목표**: 과거 회의 검색, 자연어 질의응답, 캘린더 등록

- [x] Chat Agent 구현 (RAG 기반)
- [x] SQLite FTS5 전문 검색 설정
- [x] 대화 컨텍스트 관리
- [x] /tasks, /meetings 명령어 구현
- [x] 할일 상태 변경 (/done)
- [x] Google Calendar API 연동 (텔레그램 요청 시 할일 → 캘린더 등록)

**완료 기준**: "지난주 미팅 내용 알려줘" 질문에 답변 + "캘린더에 넣어줘" 시 등록

### Phase 4: 마무리 (Day 7)
**목표**: 안정화 및 사용성 개선

- [x] 에러 핸들링 강화
- [x] 긴 메시지 분할 전송 (텔레그램 4096자 제한)
- [x] /help 도움말 완성
- [x] 기본적인 로깅
- [ ] 실제 클로바노트 데이터로 테스트
- [ ] 연구실 PC 배포 (nohup 백그라운드 실행)

---

## 6. 프롬프트 설계

### 6.1 Router 프롬프트

```
당신은 메시지 분류기입니다.
다음 메시지의 의도를 판별하세요.

카테고리:
- transcript_upload: 회의록/대화 기록 (500자 이상, 화자+시간 패턴)
- task_query: 할일/태스크 관련 질문
- meeting_search: 과거 회의 내용 검색
- calendar_register: 할일/일정을 캘린더에 등록 요청
- name_mapping: 화자 이름 설정/변경 요청
- general_chat: 일반 대화 또는 기타

메시지:
{message}

JSON으로만 응답:
{"intent": "카테고리명", "confidence": 0.0~1.0}
```

### 6.2 Parser 프롬프트

```
클로바노트로 기록된 회의록입니다. 다음 작업을 수행하세요:

1. 화자별 발언을 구분하세요
2. 타임스탬프가 있으면 추출하세요
3. 주제별로 섹션을 나누세요
4. 회의 날짜를 추정하세요 (없으면 오늘 날짜 사용)

원본:
{transcript}

JSON으로 응답:
{
  "date": "YYYY-MM-DD",
  "participants": ["화자명", ...],
  "segments": [{"speaker": "", "timestamp": "", "content": "", "topic": ""}],
  "topic_sections": [{"topic": "", "start": "", "end": ""}]
}
```

### 6.3 Summarizer 프롬프트

```
다음은 구조화된 회의 데이터입니다. 한국어로 요약하세요.

규칙:
- 핵심 논의사항: 중요도 순으로 3-5개
- 결정사항: 확정된 내용만
- 미결 이슈: 아직 결론 나지 않은 것
- 각 항목은 1-2문장으로 간결하게

회의 데이터:
{parsed_data}
```

### 6.4 Action Extractor 프롬프트

```
다음 회의 내용에서 할 일(액션 아이템)을 추출하세요.

추출 기준:
- "~하기로 했다", "~해주세요", "~까지" 등 명시적 할당
- "~가 필요하다" 등 암묵적 과제
- 담당자가 불분명하면 assignee를 null로

회의 데이터:
{parsed_data}

JSON 배열로 응답:
[{"description": "", "assignee": "", "deadline": "YYYY-MM-DD 또는 null", "priority": "high|medium|low"}]
```

### 6.5 Chat Agent 프롬프트

```
당신은 랩미팅 기록을 관리하는 AI 어시스턴트입니다.
아래 회의 기록을 참고하여 질문에 답하세요.

규칙:
- 회의 기록에 있는 내용만 근거로 답변
- 없는 내용은 "해당 내용은 기록에서 찾을 수 없습니다"로 응답
- 날짜와 화자를 명시하여 답변
- 간결하고 핵심적으로

관련 회의 기록:
{context}

사용자 질문: {question}
```

### 6.6 Calendar Register 프롬프트

```
사용자가 할일을 Google Calendar에 등록해달라고 요청했습니다.
아래 할일 목록에서 요청에 해당하는 항목을 찾아 캘린더 이벤트로 변환하세요.

규칙:
- 사용자가 특정 항목을 지정했으면 해당 항목만
- "다 넣어줘" 등이면 기한이 있는 항목 전부
- 기한이 없는 항목은 사용자에게 날짜를 물어보세요
- 제목은 간결하게, 설명에 회의 출처 포함

현재 할일 목록:
{action_items}

사용자 요청: {request}

JSON 배열로 응답:
[{"title": "", "date": "YYYY-MM-DD", "description": "출처: MM/DD 랩미팅", "needs_date_confirm": false}]
```

### 6.7 Speaker Mapper 프롬프트

```
사용자가 화자 이름을 설정하려고 합니다.
메시지에서 클로바노트 라벨과 실제 이름의 매핑을 추출하세요.

예시:
- "화자 1은 김연구원이고 화자 2는 박연구원이야" → [{"label": "화자 1", "name": "김연구원"}, ...]
- "화자1 = 이박사" → [{"label": "화자 1", "name": "이박사"}]

메시지: {message}

JSON 배열로 응답:
[{"label": "화자 N", "name": "실제이름"}]
```

---

## 7. 핵심 구현 코드 가이드

### 7.1 LLM Client 래퍼

```python
# utils/llm_client.py
import anthropic

client = anthropic.AsyncAnthropic()

async def ask_llm(
    prompt: str,
    system: str = "",
    model: str = "claude-haiku-4-5-20251001",
    max_tokens: int = 2000,
) -> str:
    """Claude API 호출 래퍼. 파싱/라우팅은 Haiku, 요약/대화는 Sonnet 사용."""
    message = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text
```

### 7.2 모델 사용 전략

| 에이전트 | 모델 | 이유 |
|----------|------|------|
| Router | Haiku | 빠른 분류, 비용 절감 |
| Parser | Haiku | 구조화 파싱은 가벼운 작업 |
| Speaker Mapper | Haiku | 이름 추출은 가벼운 작업 |
| Summarizer | Sonnet | 요약 품질 중요 |
| Action Extractor | Haiku | 패턴 추출은 가벼운 작업 |
| Chat Agent | Sonnet | 자연어 이해 + 생성 품질 |
| Calendar Register | Haiku | 할일 → 이벤트 변환은 가벼운 작업 |

### 7.3 텔레그램 메시지 핸들러 골격

```python
# bot/handlers/message_handler.py
from telegram import Update
from telegram.ext import ContextTypes
from agents.router import classify_intent
from agents.transcript_parser import parse_transcript
from agents.speaker_mapper import apply_name_mapping, set_speaker_name
from agents.summarizer import summarize_meeting
from agents.action_extractor import extract_actions
from agents.chat_agent import chat_response
from storage.database import save_meeting, save_actions

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.effective_chat.id

    # 1. 의도 분류
    intent = await classify_intent(text)

    if intent == "transcript_upload":
        # 2. 파싱 → 화자 매핑 → 요약 → 할일 추출 → 저장
        await update.message.reply_text("🔍 회의록 분석 중...")

        parsed = await parse_transcript(text)
        parsed = await apply_name_mapping(parsed, chat_id)  # 화자 이름 치환
        summary = await summarize_meeting(parsed)
        actions = await extract_actions(parsed)

        meeting_id = await save_meeting(chat_id, text, parsed, summary)
        await save_actions(meeting_id, actions)

        # 3. 응답 포맷팅 및 전송
        response = format_meeting_response(summary, actions)
        await update.message.reply_text(response, parse_mode="Markdown")

    elif intent == "name_mapping":
        # 4. 화자 이름 설정
        result = await set_speaker_name(chat_id, text)
        await update.message.reply_text(result, parse_mode="Markdown")

    elif intent == "calendar_register":
        # 5. 캘린더 등록 (사용자 명시적 요청 시에만)
        reply = await chat_response(chat_id, text, mode="calendar")
        await update.message.reply_text(reply, parse_mode="Markdown")

    else:
        # 6. 대화형 응답 (할일 조회, 회의 검색, 일반 대화)
        reply = await chat_response(chat_id, text)
        await update.message.reply_text(reply, parse_mode="Markdown")
```

### 7.4 봇 엔트리포인트

```python
# bot/main.py
import os
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters
from bot.handlers.message_handler import handle_message
from bot.handlers.command_handler import (
    cmd_start, cmd_help, cmd_tasks, cmd_meetings, cmd_setname, cmd_names
)
from storage.database import init_db

load_dotenv()

def main():
    # DB 초기화
    init_db()

    # 봇 생성
    app = ApplicationBuilder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()

    # 명령어 핸들러
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("tasks", cmd_tasks))
    app.add_handler(CommandHandler("meetings", cmd_meetings))
    app.add_handler(CommandHandler("setname", cmd_setname))
    app.add_handler(CommandHandler("names", cmd_names))

    # 일반 메시지 핸들러
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 봇 실행 중...")
    app.run_polling()

if __name__ == "__main__":
    main()
```

---

## 8. 추가 제안 기능 (MVP 이후)

| 기능 | 설명 | 우선순위 |
|------|------|----------|
| 할일 리마인더 | 기한 임박 시 텔레그램 알림 | 중간 |
| 파일 첨부 지원 | .txt, .docx 파일 업로드 처리 | 중간 |
| 다중 사용자 | 그룹 채팅에서 여러 명이 함께 사용 | 중간 |
| 임베딩 검색 | FTS5 → 벡터 DB 시맨틱 검색 | 낮음 |
| Notion/Obsidian 내보내기 | 회의록을 노트앱으로 내보내기 | 낮음 |

**유용한 외부 도구**:

| 도구 | 용도 | 비고 |
|------|------|------|
| Google Calendar API | 사용자 요청 시 할일 → 캘린더 등록 | 텔레그램에서 명시적 요청 시에만 |
| Notion API | 회의록을 Notion DB로 동기화 | 별도 구현 필요 |
| Slack Webhook | 슬랙에도 요약 전달 (듀얼 채널) | 간단한 HTTP POST |

**클로바노트 입력 최적화 팁**:
- 클로바노트 앱에서 "텍스트 복사" → 텔레그램에 붙여넣기가 가장 간편
- 클로바노트 공유 링크는 접근 제한이 있어 직접 텍스트 복사 권장
- 향후 클로바노트 API가 공개되면 자동 연동 가능

---

## 9. 환경 설정

### 9.1 필수 환경변수 (.env)

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
ANTHROPIC_API_KEY=your_anthropic_api_key
DATABASE_PATH=./data/meetings.db
GOOGLE_CALENDAR_CREDENTIALS=./credentials.json
LOG_LEVEL=INFO
```

### 9.2 의존성 (requirements.txt)

```
python-telegram-bot>=20.0
anthropic>=0.40.0
aiosqlite>=0.20.0
python-dotenv>=1.0.0
google-api-python-client>=2.100.0
google-auth-oauthlib>=1.0.0
```

### 9.3 .gitignore

```
.env
credentials.json
token.json
data/
__pycache__/
*.pyc
```

### 9.4 텔레그램 봇 생성 방법
1. 텔레그램 앱에서 `@BotFather` 검색
2. `/newbot` 명령어로 봇 생성
3. 봇 이름 설정 (예: "랩미팅 봇")
4. 봇 username 설정 (예: `labmeeting_hun_bot`, 반드시 `bot`으로 끝나야 함)
5. 발급된 API 토큰을 .env의 `TELEGRAM_BOT_TOKEN`에 저장

### 9.5 Google Calendar API 설정
1. [Google Cloud Console](https://console.cloud.google.com) 접속 → 새 프로젝트 생성
2. "API 및 서비스 → 라이브러리" → "Google Calendar API" 검색 → 사용 클릭
3. "Google Auth Platform → Branding" → 앱 이름 + 이메일 입력
4. "Audience" → 외부(External) 선택 → 테스트 사용자에 본인 Gmail 추가
5. "사용자 인증 정보 → OAuth 클라이언트 ID 만들기" → 애플리케이션 유형: 데스크톱 앱
6. JSON 다운로드 → `credentials.json`으로 이름 변경 → 프로젝트 루트에 배치
7. 최초 `python main.py` 실행 시 브라우저 인증 → `token.json` 자동 생성
8. 이후 token.json으로 자동 인증 (갱신도 자동)

> **주의**: 테스트 모드에서는 토큰이 7일마다 만료됨. 앱을 "게시(Publish)"로 전환하면 해결.

### 9.6 봇 실행 방법

**개발/테스트 (내 PC)**:
```bash
cd lab-meeting-bot
python -m bot.main
# Ctrl+C로 종료
```

**연구실 PC 상시 실행 (Linux)**:
```bash
# 백그라운드 실행 (터미널 닫아도 유지)
nohup python -m bot.main > bot.log 2>&1 &

# 로그 확인
tail -f bot.log

# 종료
ps aux | grep main.py
kill <PID>
```

**연구실 PC 상시 실행 (Windows)**:
```bash
pythonw -m bot.main
```

> 봇이 꺼져있을 때 보낸 메시지는 텔레그램 서버에 쌓여있다가 봇을 다시 켜면 한꺼번에 처리됩니다.

---

## 10. Claude Code 작업 지시

> 이 문서를 Claude Code에 전달할 때 아래 순서로 요청하세요.

### 작업 순서
1. **"Phase 1부터 시작하자. 프로젝트 구조 만들고 텔레그램 봇 기본 연결해줘."**
2. **"Phase 2 진행. Router → Parser → Speaker Mapper → Summarizer → Action Extractor 순서로 구현해줘. 화자 이름 매핑은 /setname 명령어와 대화 방식 둘 다 지원해."**
3. **"Phase 3 진행. Chat Agent, 검색 기능, Google Calendar 연동 구현해줘. 캘린더는 텔레그램에서 요청할 때만 등록하는 방식으로."**
4. **"Phase 4. 에러 핸들링 보강하고 실제 클로바노트 데이터로 테스트해보자."**

### 주의사항
- 각 Phase 완료 후 동작 테스트 → 다음 Phase 진행
- 프롬프트는 6장의 템플릿을 기본으로 사용하되, 실제 데이터로 튜닝 필요
- Claude API 호출 시 모델 선택은 7.2 표 참고
- 텔레그램 4096자 제한 주의 (긴 응답은 분할 전송)
- 화자 이름 매핑은 처음 한 번만 설정하면 이후 회의록에 자동 적용
- 캘린더 등록은 자동 아님 — 반드시 사용자가 텔레그램에서 요청해야 동작
- 개발 중에는 내 PC에서 `python -m bot.main`으로 테스트, 완성 후 연구실 PC에 배포
