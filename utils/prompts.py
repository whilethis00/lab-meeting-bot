ROUTER_PROMPT = """당신은 메시지 분류기입니다.
다음 메시지의 의도를 판별하세요.

카테고리:
- transcript_upload: 회의록/대화 기록 (500자 이상, 화자+시간 패턴)
- task_query: 할 일/태스크 관련 질문
- meeting_search: 과거 회의 내용 검색
- calendar_register: 할 일/일정을 캘린더에 등록 요청
- name_mapping: 화자 이름 설정/변경 요청
- general_chat: 일반 대화 또는 기타

메시지가 500자 이상이고 "화자"/"Speaker"와 시간 형식이 보이면 transcript_upload입니다.
"캘린더", "일정 등록", "캘린더에 넣어" 등이면 calendar_register입니다.
"화자 1은 ~", "이름 설정" 등이면 name_mapping입니다.

메시지:
{message}

JSON으로만 응답:
{{"intent": "카테고리명", "confidence": 0.0~1.0}}"""


PARSER_PROMPT = """클로바노트 또는 다글로로 기록된 회의록입니다. 다음 작업을 수행하세요:

포맷 안내:
- 클로바노트: "화자 N HH:MM:SS\n내용"
- 다글로: "MM:SS Speaker N\n내용"


1. 화자별 발언을 구분하세요
2. 타임스탬프가 있으면 추출하세요
3. 주제별로 섹션을 나누세요
4. 회의 날짜를 추론하세요 (없으면 오늘 날짜 사용: {today})

원본:
{transcript}

JSON으로 응답:
{{
  "date": "YYYY-MM-DD",
  "participants": ["화자명", ...],
  "segments": [
    {{"speaker": "", "timestamp": "", "content": "", "topic": ""}}
  ],
  "topic_sections": [
    {{"topic": "", "start": "", "end": ""}}
  ],
  "duration_minutes": 숫자
}}"""


SUMMARIZER_PROMPT = """다음은 구조화된 회의 데이터입니다. 한국어로 요약하세요.

규칙:
- 핵심 논의사항: 중요도 순으로 3-5개
- 결정 사항: 확정된 내용만
- 미결 이슈: 아직 결론 나지 않은 것
- 각 항목은 1-2문장으로 간결하게

회의 데이터:
{parsed_data}"""


ACTION_EXTRACTOR_PROMPT = """다음 회의 내용에서 할 일(액션 아이템)을 추출하세요.

추출 기준:
- "~하기로 했다", "~해주세요", "~까지" 등 명시적 할당
- "~가 필요하다" 등 암묵적 과제 (관련 화자에게 배정)
- 담당자가 불분명하면 assignee를 null로

회의 데이터:
{parsed_data}

JSON 배열로 응답:
[
  {{
    "description": "할 일 내용",
    "assignee": "담당자 이름 또는 null",
    "deadline": "YYYY-MM-DD 또는 null",
    "priority": "high|medium|low"
  }}
]"""


CHAT_AGENT_PROMPT = """당신은 랩미팅 기록을 관리하는 AI 어시스턴트입니다.
아래 회의 기록을 참고하여 질문에 답하세요.

규칙:
- 회의 기록에 있는 내용만 근거로 답변
- 없는 내용은 "해당 내용을 기록에서 찾을 수 없습니다"로 응답
- 날짜와 회의를 명시하여 답변
- 간결하고 핵심적으로

관련 회의 기록:
{context}

사용자 질문: {question}"""


CALENDAR_REGISTER_PROMPT = """사용자가 할 일을 Google Calendar에 등록해달라고 요청했습니다.
아래 할 일 목록에서 요청에 해당하는 항목을 찾아 캘린더 이벤트로 변환하세요.

규칙:
- 사용자가 특정 항목을 지정했으면 해당 항목만
- "다 넣어줘" 등이면 기한이 있는 항목 전부
- 기한이 없는 항목은 needs_date_confirm을 true로
- 제목은 간결하게, 설명에 출처 회의 포함

현재 할 일 목록:
{action_items}

사용자 요청: {request}

JSON 배열로 응답:
[{{"title": "", "date": "YYYY-MM-DD 또는 null", "description": "출처: MM/DD 랩미팅", "needs_date_confirm": false}}]"""


SPEAKER_MAPPER_PROMPT = """사용자가 화자 이름을 설정하려고 합니다.
메시지에서 클로바노트 라벨과 실제 이름 매핑을 추출하세요.

예시:
- "화자 1은 김연구원이고 화자 2는 박연구원이야" → [{{"label": "화자 1", "name": "김연구원"}}, {{"label": "화자 2", "name": "박연구원"}}]
- "화자1 = 이박사" → [{{"label": "화자 1", "name": "이박사"}}]
- "Speaker 1은 김연구원이야" → [{{"label": "Speaker 1", "name": "김연구원"}}]

메시지: {message}

JSON 배열로 응답:
[{{"label": "화자 N", "name": "실제이름"}}]"""
