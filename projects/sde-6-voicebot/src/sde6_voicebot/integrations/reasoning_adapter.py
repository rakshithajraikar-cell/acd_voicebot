"""Reasoning Proposal Adapter (W3 -> W4 Integration).

Transforms ReasoningResult and WorkflowProposal outputs from Workstream W3
(Context, Vision & Reasoning by Prathibhashree K) into validated, dependency-managed
WorkflowPlan instances for execution by W4.
"""

from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from sde6_voicebot.contracts.workflow import (
    WorkflowPlan,
    WorkflowProposal,
    WorkflowStep,
)


class ReasoningProposalAdapter:
    """Adapter that converts reasoning outputs and proposals into executable WorkflowPlans."""

    @classmethod
    def proposal_to_plan(
        cls,
        proposal: WorkflowProposal,
        title: Optional[str] = None,
    ) -> WorkflowPlan:
        """Convert a strongly-typed WorkflowProposal directly into a WorkflowPlan.
        
        Args:
            proposal: The WorkflowProposal object from Reasoning
            title: Optional custom title override
            
        Returns:
            A validated WorkflowPlan
        """
        plan_title = title or f"Workflow for {proposal.intent}"
        description = (
            f"Automated workflow initiated by reasoning proposal {proposal.proposal_id}.\n"
            f"Intent: {proposal.intent}\n"
            f"Confidence: {proposal.confidence:.2f}\n"
            f"Suggested Action: {proposal.suggested_action or 'N/A'}"
        )

        steps = list(proposal.steps)
        if not steps and proposal.suggested_action:
            # Synthesize steps from suggested_action
            steps = cls._synthesize_steps_from_text(
                proposal.suggested_action,
                context_data=proposal.sources_used,
            )

        if not steps:
            # Default fallback harmless step
            steps = [
                WorkflowStep(
                    step_id="step-1-notes",
                    name="Format Context Notes",
                    tool_name="format_notes",
                    arguments={"text": f"Context for intent: {proposal.intent}"},
                    is_consequential=False,
                    is_idempotent=True,
                )
            ]

        return WorkflowPlan(
            plan_id=str(uuid4()),
            session_id=proposal.session_id,
            correlation_id=proposal.correlation_id,
            title=plan_title,
            description=description,
            steps=steps,
        )

    @classmethod
    def reasoning_result_to_plan(
        cls,
        reasoning_result: Any,
        session_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        title: Optional[str] = None,
    ) -> WorkflowPlan:
        """Convert a ReasoningResult (dataclass or dict) from W3 into a WorkflowPlan.
        
        Args:
            reasoning_result: ReasoningResult object or dictionary
            session_id: Session ID override if not present in result
            correlation_id: Correlation ID override if not present in result
            title: Optional title override
            
        Returns:
            Validated WorkflowPlan
        """
        # Support both dataclass object and raw dict
        if hasattr(reasoning_result, "to_dict"):
            data = reasoning_result.to_dict()
        elif isinstance(reasoning_result, dict):
            data = reasoning_result
        else:
            data = {
                "session_id": getattr(reasoning_result, "session_id", str(uuid4())),
                "correlation_id": getattr(reasoning_result, "correlation_id", str(uuid4())),
                "response_text": getattr(reasoning_result, "response_text", ""),
                "suggested_action": getattr(reasoning_result, "suggested_action", None),
                "confidence": getattr(reasoning_result, "confidence", 1.0),
                "sources_used": getattr(reasoning_result, "sources_used", []),
            }

        sid = data.get("session_id") or session_id or str(uuid4())
        cid = data.get("correlation_id") or correlation_id or str(uuid4())
        suggested = data.get("suggested_action") or data.get("response_text", "")
        sources = data.get("sources_used", [])

        steps = cls._synthesize_steps_from_text(suggested, context_data=sources)
        if not steps:
            steps = [
                WorkflowStep(
                    step_id="step-1-format",
                    name="Format Reasoning Response",
                    tool_name="format_notes",
                    arguments={"text": data.get("response_text", "Grounded response notes")},
                    is_consequential=False,
                    is_idempotent=True,
                )
            ]

        plan_title = title or "Reasoning-Derived Workflow Plan"
        plan_desc = (
            f"Derived from ReasoningResult. Confidence: {data.get('confidence', 1.0):.2f}. "
            f"Sources cited: {len(sources)}."
        )

        return WorkflowPlan(
            plan_id=str(uuid4()),
            session_id=sid,
            correlation_id=cid,
            title=plan_title,
            description=plan_desc,
            steps=steps,
        )

    @classmethod
    def _synthesize_steps_from_text(
        cls,
        text: str,
        context_data: Optional[List[Any]] = None,
    ) -> List[WorkflowStep]:
        """Synthesize dependency-managed workflow steps from reasoning action text."""
        lowered = text.lower()
        steps: List[WorkflowStep] = []

        has_format = "format" in lowered or "notes" in lowered or "summarize" in lowered or "transcription" in lowered
        has_reminder = "reminder" in lowered or "schedule" in lowered or "follow-up" in lowered

        if has_format:
            steps.append(
                WorkflowStep(
                    step_id="step-1-format",
                    name="Format Lecture & Session Notes",
                    tool_name="format_notes",
                    arguments={"text": text},
                    is_consequential=False,
                    is_idempotent=True,
                    idempotency_key=f"format-{hash(text) % 100000}",
                )
            )

        if has_reminder:
            reminder_step = WorkflowStep(
                step_id="step-2-reminder",
                name="Schedule Follow-up Reminder",
                tool_name="schedule_reminder",
                arguments={
                    "title": "Review AI Voicebot Session Notes",
                    "delay_minutes": 60,
                    "priority": "normal",
                },
                depends_on=["step-1-format"] if has_format else [],
                is_consequential=True,
                is_idempotent=False,
                idempotency_key=f"reminder-{hash(text) % 100000}",
            )
            steps.append(reminder_step)

        return steps
