"""Integration layer for Workstream W4 (Agentic Workflow).

Provides bridges and adapters for cross-team integration:
- reasoning_adapter: Ingests WorkflowProposal and ReasoningResult from W3 (Prathibhashree K)
- backend_bridge: Connects approval states and audit records to W5 Backend (Radhika B)
- ui_controller: Connects interactive approvals, progress events, and rejections to W6 Frontend (Shivani Adaragunchi)
"""

from sde6_voicebot.integrations.reasoning_adapter import ReasoningProposalAdapter
from sde6_voicebot.integrations.backend_bridge import BackendApprovalBridge
from sde6_voicebot.integrations.ui_controller import UIWorkflowController

__all__ = [
    "ReasoningProposalAdapter",
    "BackendApprovalBridge",
    "UIWorkflowController",
]
