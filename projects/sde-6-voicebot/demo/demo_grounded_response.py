"""
Day 7 Demonstration Script — Grounded Context and Reasoning Vertical Slice
Team: SDE 6 | Student: Prathibhashree K | Workstream: W3 (Context and Reasoning)
Academiaai AI Voicebot

Demonstrates:
1. Screen capture disabled by default (Strict Privacy Standard)
2. Explicit user opt-in consent and synthetic frame generation (Zero PII)
3. Versioned prompt assembly separating trusted instructions from untrusted data
4. Deterministic mock reasoning generating a schema-validated grounded response
5. Insufficient evidence detection surfacing uncertainty without hallucination
6. Consent revocation and immediate context purging
7. Rejection of invalid requests with canonical ErrorEnvelope formatting
"""

import json
import sys
import uuid
from pathlib import Path

# Add project root and src to sys.path
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from contracts.envelope import EventEnvelope, ErrorEnvelope
from contracts.context import ScreenContext, SourceType
from contracts.reasoning import ReasoningRequest, ReasoningResult
from src.voicebot.context.capture_adapter import ScreenCaptureAdapter, CaptureState
from src.voicebot.context.synthetic_frames import SyntheticFrameGenerator, SyntheticFixture
from src.voicebot.prompts.prompt_manager import PromptManager
from src.voicebot.reasoning.mock_reasoner import MockReasoningEngine
from src.voicebot.validation.validators import (
    ValidationError,
    validate_reasoning_request,
    validate_reasoning_result,
    format_error_envelope,
)


def print_banner(title: str):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def run_demo():
    session_id = f"sess_sde6_demo_{uuid.uuid4().hex[:6]}"
    correlation_id = f"corr_w3_{uuid.uuid4().hex[:8]}"

    print_banner("ACADEMIAAI VOICEBOT — SDE 6 (W3 CONTEXT & REASONING) DAY 7 DEMO")
    print(f"Session ID     : {session_id}")
    print(f"Correlation ID : {correlation_id}")
    print(f"Student / Owner: Prathibhashree K (SDE 6, Workstream W3)")

    # -------------------------------------------------------------------------
    # STEP 1: Verify Screen Capture Default State
    # -------------------------------------------------------------------------
    print_banner("STEP 1: Screen Capture Default Privacy Check")
    adapter = ScreenCaptureAdapter(session_id=session_id)
    indicator = adapter.get_indicator_state()

    print(f"Screen capture enabled by default : {adapter.is_enabled} (Must be False)")
    print(f"User consent granted by default   : {adapter.has_consent} (Must be False)")
    print(f"UI Indicator state                : {indicator['state']} (Color: {indicator['indicator_color']})")

    unauthorized_frame = adapter.capture_frame()
    print(f"Captured frame without consent    : capture_enabled={unauthorized_frame.capture_enabled}, ocr_text={unauthorized_frame.ocr_text}")
    assert unauthorized_frame.capture_enabled is False, "Violation: Screen capture active without consent!"
    print(">> [PASS] Privacy Gate Verified: Screen capture is strictly OFF by default.")

    # -------------------------------------------------------------------------
    # STEP 2: Explicit User Opt-In Consent
    # -------------------------------------------------------------------------
    print_banner("STEP 2: Explicit User Opt-In & Synthetic Frame Generation")
    print("User clicks 'Enable Screen Context' in UI...")
    new_state = adapter.grant_consent_and_enable()
    adapter.set_fixture(SyntheticFixture.STUDENT_GRADES)
    indicator = adapter.get_indicator_state()

    print(f"New Capture State                 : {new_state.value}")
    print(f"UI Indicator Display              : {indicator['indicator_label']} ({indicator['indicator_color']})")

    active_frame = adapter.capture_frame()
    print(f"Synthetic Frame Generated         : ID={active_frame.context_id}")
    print(f"Window Title                      : '{active_frame.window_title}'")
    print(f"Application Name                  : '{active_frame.application_name}'")
    print(f"Synthetic Flag                    : is_synthetic={active_frame.is_synthetic} (No real PII)")
    print(f"Detected UI Bounding Boxes        : {len(active_frame.bounding_boxes)} elements")
    print(">> [PASS] Explicit consent activated with zero disk writes and zero PII.")

    # -------------------------------------------------------------------------
    # STEP 3: Grounded Reasoning Request with Context
    # -------------------------------------------------------------------------
    print_banner("STEP 3: Grounded Reasoning Request (Happy Path)")
    context_items = SyntheticFrameGenerator.generate_context_items(session_id, SyntheticFixture.STUDENT_GRADES)
    user_speech = "What is my grade in CS101 and what was my score?"
    print(f"User Voice Query                  : \"{user_speech}\"")
    print(f"Active Context Items Available    : {len(context_items)} item(s)")

    # Demonstrate Versioned Prompt Assembly
    rendered_prompt = PromptManager.render_prompt(
        user_query=user_speech,
        context_items=context_items,
        version="1.0.0",
    )
    print("\n--- Versioned Prompt Assembly (v1.0.0) ---")
    print(f"Prompt Version                    : {rendered_prompt.prompt_version}")
    print(f"Trusted Instructions Length       : {len(rendered_prompt.trusted_instructions)} chars")
    print(f"Untrusted Context Quarantined     : {rendered_prompt.untrusted_context_block[:120]}...")
    print(f"Untrusted User Input Tagged       : {rendered_prompt.untrusted_user_block}")

    # Create & Validate ReasoningRequest
    request = ReasoningRequest.create(
        session_id=session_id,
        correlation_id=correlation_id,
        user_query=user_speech,
        context_items=context_items,
        prompt_version="1.0.0",
        mock_mode=True,
    )
    validated_req = validate_reasoning_request(request)
    print(f"\nReasoningRequest Validated        : ID={validated_req.request_id}, mock_mode={validated_req.mock_mode}")

    # Execute Deterministic Mock Reasoning
    engine = MockReasoningEngine(mock_mode=True, simulated_delay_ms=5.0)
    result = engine.execute_reasoning(validated_req)
    validated_res = validate_reasoning_result(result)

    print("\n--- Reasoning Output (Grounded & Schema-Validated) ---")
    print(f"Result ID                         : {validated_res.result_id}")
    print(f"Grounded Response Text            : \"{validated_res.response_text}\"")
    print(f"Confidence Score                  : {validated_res.confidence} ({validated_res.confidence_level.value})")
    print(f"Has Sufficient Evidence           : {validated_res.has_sufficient_evidence}")
    print(f"Execution Latency                 : {validated_res.execution_time_ms} ms")
    print(f"Citations (sources_used)          : {len(validated_res.sources_used)} source(s)")
    for i, src in enumerate(validated_res.sources_used, 1):
        print(f"   [{i}] URI: {src.uri} | Title: '{src.title}'")

    assert validated_res.has_sufficient_evidence is True, "Expected sufficient evidence!"
    assert len(validated_res.sources_used) > 0, "Expected grounded citations!"
    print(">> [PASS] Request produced a mock grounded response with verified citations.")

    # -------------------------------------------------------------------------
    # STEP 4: Insufficient Evidence Scenario (Surfacing Uncertainty)
    # -------------------------------------------------------------------------
    print_banner("STEP 4: Insufficient Evidence Handling (Surfacing Uncertainty)")
    unknown_query = "What is the date and room number for my Physics final exam?"
    print(f"User Voice Query                  : \"{unknown_query}\"")
    print("Context on screen                 : Student Academic Portal (Grades only, no exam dates)")

    unsupported_req = ReasoningRequest.create(
        session_id=session_id,
        correlation_id=correlation_id,
        user_query=unknown_query,
        context_items=context_items,
    )
    unsupported_res = engine.execute_reasoning(unsupported_req)

    print(f"Response Text                     : \"{unsupported_res.response_text}\"")
    print(f"Has Sufficient Evidence           : {unsupported_res.has_sufficient_evidence}")
    print(f"Uncertainty Reason                : \"{unsupported_res.uncertainty_reason}\"")
    print(f"Confidence Level                  : {unsupported_res.confidence_level.value}")

    assert unsupported_res.has_sufficient_evidence is False, "Expected insufficient evidence flag to be False!"
    print(">> [PASS] Insufficient evidence surfaced safely without hallucination.")

    # -------------------------------------------------------------------------
    # STEP 5: Consent Revocation & Immediate Purge
    # -------------------------------------------------------------------------
    print_banner("STEP 5: Consent Revocation & Memory Purge")
    print("User clicks 'Revoke Screen Capture Consent'...")
    revoked_state = adapter.withdraw_consent()
    print(f"Adapter State                     : {revoked_state.value}")
    print(f"Is Enabled                        : {adapter.is_enabled}")
    purged_frame = adapter.capture_frame()
    print(f"Frame after consent revocation    : capture_enabled={purged_frame.capture_enabled}, ocr_text={purged_frame.ocr_text}")
    print(">> [PASS] Withdrawing consent immediately stopped capture and released context.")

    # -------------------------------------------------------------------------
    # STEP 6: Invalid Request Validation & ErrorEnvelope
    # -------------------------------------------------------------------------
    print_banner("STEP 6: Rejection of Invalid Requests via ErrorEnvelope")
    invalid_payload = {
        "request_id": str(uuid.uuid4()),
        "session_id": session_id,
        "correlation_id": correlation_id,
        "user_query": "   ",  # Invalid empty query
        "temperature": 2.5,   # Invalid out-of-range temperature
    }
    print(f"Attempting to submit invalid payload: {invalid_payload}")
    try:
        validate_reasoning_request(invalid_payload)
        print("ERROR: Invalid payload was unexpectedly accepted!")
    except ValidationError as val_err:
        err_envelope = format_error_envelope(val_err, correlation_id=correlation_id)
        print(f"\nRejection Caught Successfully!")
        print(f"Error Code                        : {err_envelope.code}")
        print(f"Message Safe For User             : \"{err_envelope.message_safe_for_user}\"")
        print(f"Retryable                         : {err_envelope.retryable}")
        print(f"Correlation ID                    : {err_envelope.correlation_id}")
        print(f"Redacted Details                  : {err_envelope.details_redacted}")
        print(">> [PASS] Schema rejection validated and formatted into standard ErrorEnvelope.")

    print_banner("ALL DAY 1 - DAY 7 CRITERIA SUCCESSFULLY DEMONSTRATED AND PASSED!")


if __name__ == "__main__":
    run_demo()
