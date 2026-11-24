# Developer Guide: Adding a Safe Tool

**Workstream:** W4 (Agentic Workflow Engine)  
**Standard:** Section 8 Engineering Standards & Mock Mode Purity  
**Author:** Spoorthi Y D (`ydspoorthi24-sys`)

---

## 1. Safety Principles & Mandatory Constraints

When introducing a new tool to the voicebot workflow engine, you MUST adhere to the following strict safety principles:

1. **Mock Mode Purity**: The tool MUST NOT make real network calls, write real files outside isolated scratch dirs, or execute computer control.
2. **Schema Definition Once**: All schemas must be strongly typed using Pydantic and defined in accordance with project contracts.
3. **Explicit Consequentiality**: If a tool has persistent consequences, updates state, or sends notifications, `is_consequential` MUST be set to `True`.
4. **Idempotency Classification**: Only safe read/transform operations may be declared `is_idempotent=True`. Non-idempotent operations must never be retried automatically.
5. **Granular Permission Scope**: Every tool must declare a distinct, namespaced permission scope (e.g. `domain.subsystem.action`).

---

## 2. Step-by-Step Implementation Checklist

### Step 1: Define the `ToolSpec` in `workflow/tools.py`
Declare the tool specification including parameter schema and security metadata:

```python
NEW_TOOL_SPEC = ToolSpec(
    tool_id="tool.summarize_transcript",
    name="summarize_transcript",
    description="Summarizes an audio transcript into bullet points.",
    parameters_schema={
        "type": "object",
        "required": ["transcript_text"],
        "properties": {
            "transcript_text": {"type": "string", "description": "Raw speech-to-text text"},
            "max_bullets": {"type": "integer", "minimum": 1, "default": 5},
        },
    },
    is_consequential=False,
    is_idempotent=True,
    permission_scope="safe.transcript.read",
    version="1.0.0",
)
```

### Step 2: Implement the Pure Harmless Handler
Handlers must take `args: Dict[str, Any]` and return `Dict[str, Any]`:

```python
def _execute_summarize_transcript(args: Dict[str, Any]) -> Dict[str, Any]:
    text = args["transcript_text"]
    max_bullets = args.get("max_bullets", 5)
    # Perform deterministic in-memory transformation
    lines = [line.strip() for line in text.split(".") if line.strip()]
    bullets = lines[:max_bullets]
    return {
        "bullets": bullets,
        "count": len(bullets),
    }
```

### Step 3: Register in `ToolRegistry` and `PolicyMatrix`
1. In `workflow/tools.py`:
   - Add tool name to `ToolRegistry.ALLOWED_TOOL_NAMES`.
   - Add `_specs` and `_executors` mappings in `ToolRegistry.__init__`.
2. In `workflow/policy_matrix.py`:
   - Add a `PolicyRule` specifying `RiskLevel`, `requires_human_approval`, and `max_timeout_seconds`.

### Step 4: Write Unit & Failure-Injection Tests
Every tool requires tests in `tests/`:
- **Schema & parameter validation**: Test with missing arguments, invalid types, boundary values.
- **Scope enforcement**: Verify unauthorized callers are rejected with `PermissionScopeError`.
- **Approval verification**: If consequential, verify execution halts at `AWAITING_APPROVAL` and rejection guarantees zero tool execution.
- **Idempotency verification**: Test that duplicate calls return cached outputs.

---

## 3. Code Review Checklist for Safe Tools

- [ ] Does the tool strictly operate in mock mode without external side effects?
- [ ] Is `parameters_schema` complete with required fields and types?
- [ ] Is `is_consequential` explicitly declared (`True` if stateful)?
- [ ] Is `is_idempotent` accurately set (`False` for consequential mutations)?
- [ ] Is the tool registered in `PolicyMatrix` with proper risk classification?
- [ ] Are 100% of unit and failure-injection tests passing?
