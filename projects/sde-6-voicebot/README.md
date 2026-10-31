# Academiaai AI Voicebot — Team SDE 6

## Workstream W3: Context and Reasoning Layer (Week 1 / Days 1–7)
**Student:** Prathibhashree K  
**Team Branch:** `team/sde-6-voicebot`  
**Feature Branch:** `feature/w3-context-schemas`  
**Status:** Completed & Tested

---

## 1. Overview & Architecture
This subsystem provides the typed schemas, privacy-preserving synthetic frame generation, versioned prompt management, deterministic mock reasoning, and strict validation engine for the Academiaai Voicebot.

Everything operates completely in **mock mode** with **zero paid API keys, zero external network calls, zero disk writes for frames, and zero real personal data**.

### Component Architecture
```
projects/sde-6-voicebot/
├── contracts/                        # Single source of truth for schemas & envelopes
│   ├── envelope.py                   # EventEnvelope, ErrorEnvelope, SessionState, WorkflowState
│   ├── context.py                    # ScreenContext, ContextItem, SourceReference, BoundingBox
│   └── reasoning.py                  # ReasoningRequest, ReasoningResult, ConfidenceLevel, ProviderStatus
├── src/voicebot/
│   ├── context/                      # Screen context capture & synthetic frame engine
│   │   ├── capture_adapter.py        # Privacy gatekeeper (Screen capture OFF by default, opt-in/opt-out)
│   │   └── synthetic_frames.py       # In-memory synthetic fixtures (Grades, Schedule, Library)
│   ├── prompts/                      # Prompt engineering & security quarantine
│   │   └── prompt_manager.py         # Versioned prompts (v1.0.0, v1.1.0) separating trusted/untrusted
│   ├── reasoning/                    # Deterministic mock reasoning engine
│   │   └── mock_reasoner.py          # Grounded reasoning, SourceReference citations, uncertainty surfacing
│   └── validation/                   # Schema validation & error reporting
│       └── validators.py             # Rejection of invalid inputs, format_error_envelope
├── tests/                            # 30 Unit Tests covering normal, boundary & edge cases
│   ├── test_schemas.py
│   ├── test_synthetic_frames.py
│   ├── test_prompts.py
│   ├── test_mock_reasoning.py
│   └── test_validation.py
├── demo/                             # Day 7 Live Vertical Slice Demonstration
│   └── demo_grounded_response.py
└── README.md                         # Complete documentation & field specifications
```

---

## 2. Typed Schema Specifications

Each schema is defined once inside `projects/sde-6-voicebot/contracts/` in accordance with Section 8 Engineering Standards.

### A. ScreenContext (`contracts/context.py`)
| Field | Type | Units / Format | Constraints | Description |
|---|---|---|---|---|
| `context_id` | `str` | UUID v4 | Non-empty string | Unique identifier for screen context capture |
| `session_id` | `str` | UUID v4 | Non-empty string | Session identifier for correlating with voice stream |
| `timestamp` | `str` | ISO 8601 UTC | Valid ISO date | Exact timestamp of frame generation |
| `capture_enabled` | `bool` | Boolean | **Default: False** | Non-negotiable product rule: OFF by default |
| `capture_allowed_by_user`| `bool` | Boolean | **Default: False** | Requires explicit opt-in user consent action |
| `window_title` | `Optional[str]`| UTF-8 string | Optional | Synthetic active window title |
| `application_name` | `Optional[str]`| UTF-8 string | Optional | Synthetic application name (e.g. `MockBrowser`) |
| `screen_width` | `int` | Pixels | `> 0`, default 1920 | Display width |
| `screen_height` | `int` | Pixels | `> 0`, default 1080 | Display height |
| `ocr_text` | `Optional[str]`| UTF-8 text | None if capture off | Extracted text from synthetic frame |
| `bounding_boxes` | `List[BoundingBox]`| Coordinate list | Default `[]` | Spatial layout of detected UI elements |
| `is_synthetic` | `bool` | Boolean | **Must be True** | Security guarantee: no real screenshots permitted |
| `metadata` | `Dict[str, Any]`| Key-value dictionary | None | Non-sensitive runtime operational tags |

### B. ContextItem (`contracts/context.py`)
| Field | Type | Units / Format | Constraints | Description |
|---|---|---|---|---|
| `item_id` | `str` | UUID v4 | Non-empty string | Unique identifier for the context item |
| `item_type` | `ContextItemType` | Enum | `screen_frame`, `ocr_text`, etc. | Semantic categorization |
| `content` | `str` | UTF-8 text | Non-empty string | Textual observation or extracted content |
| `source` | `SourceReference`| Object | Valid SourceReference | Provenance reference for explainability & citations |
| `confidence` | `float` | Ratio | `0.0 <= confidence <= 1.0` | Extraction confidence score |
| `created_at` | `str` | ISO 8601 UTC | Valid ISO date | Timestamp of item generation |
| `ttl_seconds` | `Optional[int]`| Seconds | `ttl_seconds >= 0` | Expiration lifetime for stale context eviction |
| `is_synthetic` | `bool` | Boolean | **Must be True** | Verifies mock synthetic origin |

### C. SourceReference (`contracts/context.py`)
| Field | Type | Units / Format | Constraints | Description |
|---|---|---|---|---|
| `source_id` | `str` | String ID | Non-empty string | Unique citation identifier |
| `source_type` | `SourceType` | Enum | `synthetic_screen`, etc. | Origin classification |
| `uri` | `Optional[str]` | URI format | e.g. `synthetic://...` | Synthetic resource locator |
| `title` | `Optional[str]` | UTF-8 string | Optional | Human-readable title of the source document |
| `snippet` | `Optional[str]` | UTF-8 text | Optional | Verbatim text excerpt supporting the claim |
| `bounding_box` | `Optional[BoundingBox]` | Pixels | Optional | Bounding coordinates on synthetic frame |
| `timestamp` | `str` | ISO 8601 UTC | Valid ISO date | Time when source was observed |

### D. ReasoningRequest (`contracts/reasoning.py`)
| Field | Type | Units / Format | Constraints | Description |
|---|---|---|---|---|
| `request_id` | `str` | UUID v4 | Non-empty string | Unique identifier for reasoning invocation |
| `session_id` | `str` | UUID v4 | Non-empty string | Voicebot session identifier |
| `correlation_id`| `str` | UUID v4 | Non-empty string | Tracing ID linking audio, STT, and reasoning |
| `user_query` | `str` | UTF-8 string | Non-empty string | Transcribed user query or voice prompt |
| `context_items`| `List[ContextItem]`| List | Optional | Active context items available to reasoning |
| `prompt_version`| `str` | SemVer string | e.g. `1.0.0` or `1.1.0` | Versioned prompt template selector |
| `temperature` | `float` | Float | `0.0 <= temp <= 1.0` (Default: 0.0) | Deterministic mock reasoning |
| `max_tokens` | `int` | Count | `> 0` (Default: 1024) | Maximum token budget |
| `mock_mode` | `bool` | Boolean | **Default: True** | Forces offline mock execution |
| `metadata` | `Dict[str, Any]`| Key-value dictionary | None | Additional tags |

### E. ReasoningResult (`contracts/reasoning.py`)
| Field | Type | Units / Format | Constraints | Description |
|---|---|---|---|---|
| `result_id` | `str` | UUID v4 | Non-empty string | Unique identifier for the reasoning result |
| `request_id` | `str` | UUID v4 | Correlates to request | Identifier of the originating request |
| `session_id` | `str` | UUID v4 | Non-empty string | Session identifier |
| `correlation_id`| `str` | UUID v4 | Non-empty string | Cross-module tracing identifier |
| `response_text`| `str` | UTF-8 text | Non-empty string | Grounded response or uncertainty statement |
| `sources_used` | `List[SourceReference]`| Citation list | Optional | Citations backing the factual claim |
| `confidence` | `float` | Ratio | `0.0 <= confidence <= 1.0` | Numerical confidence score |
| `confidence_level`| `ConfidenceLevel`| Enum | `high`, `medium`, `low`, `unknown` | Categorical confidence bucket |
| `has_sufficient_evidence`| `bool` | Boolean | True / False | Explicit flag for grounding sufficiency |
| `uncertainty_reason`| `Optional[str]`| UTF-8 string | Required if has_sufficient_evidence is False | Reason explaining missing evidence |
| `suggested_action`| `Optional[str]`| String ID | Optional | Suggested workflow proposal for W4 |
| `prompt_version`| `str` | SemVer string | Must match request | Prompt version used |
| `execution_time_ms`| `float` | Milliseconds | `>= 0.0` | Measured execution latency |
| `is_mock` | `bool` | Boolean | **Always True** | Confirms mock execution |

### F. Shared Envelopes (`contracts/envelope.py`)
- **`EventEnvelope`**: `event_id`, `event_type`, `schema_version`, `session_id`, `correlation_id`, `timestamp`, `producer`, `payload`
- **`ErrorEnvelope`**: `code`, `message_safe_for_user`, `retryable`, `correlation_id`, `details_redacted`
- **`SessionState`**: `created`, `active`, `paused`, `stopping`, `completed`, `failed`, `expired`
- **`WorkflowState`**: `draft`, `awaiting_approval`, `running`, `paused`, `succeeded`, `failed`, `cancelled`

---

## 3. Privacy, Security & Prompt Defense
1. **Screen Capture Disabled by Default**: `capture_enabled` is initialized to `False`. The `ScreenCaptureAdapter` will not capture or expose visual data until `grant_consent_and_enable()` is invoked.
2. **Consent Revocation**: Calling `withdraw_consent()` immediately revokes consent, pauses capture, and purges stored frames from memory.
3. **Synthetic Only**: Strictly zero real screenshots, zero webcams, and zero file writes.
4. **Quarantine & Anti-Injection**:
   - Prompts use explicit XML tags: `<untrusted_context>` and `<untrusted_user_query>`.
   - User inputs containing angle brackets are HTML-escaped.
   - Known prompt injection vectors (e.g. "Ignore previous instructions", "System override") are detected, neutralized, and rejected with a security notice.

---

## 4. How to Run Unit Tests & Demonstration

### Prerequisites
Python 3.10+ (Standard library only; zero external dependencies required).

### Running Unit Tests (30 Tests)
```powershell
python -m unittest discover -s tests -v
```

### Running the Live Vertical Slice Demo
```powershell
python demo/demo_grounded_response.py
```

---

## 5. Daily Progress Report Summary (Week 1 / Days 1–7)
- **Day 1–2**: Defined typed schemas (`ScreenContext`, `ContextItem`, `SourceReference`, `ReasoningRequest`, `ReasoningResult`, `EventEnvelope`, `ErrorEnvelope`) with complete field documentation, units, constraints, and immutability.
- **Day 3–4**: Implemented `ScreenCaptureAdapter` (OFF by default, opt-in/opt-out), `SyntheticFrameGenerator` (four fixtures: grades, schedule, loans, blank), `PromptManager` (versioned v1.0.0 and v1.1.0 with strict isolation and injection defense), and deterministic `MockReasoningEngine`.
- **Day 5–6**: Built comprehensive `validators.py` and unit test suite with 30 tests covering valid, boundary, invalid, and edge cases. 100% pass rate.
- **Day 7**: Created Day 7 live demo script `demo_grounded_response.py`, verified all acceptance criteria, and prepared pull request branch.
