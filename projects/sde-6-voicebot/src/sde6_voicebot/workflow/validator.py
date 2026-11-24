"""Workflow plan validator for dependencies, cycle detection, tool allow-list, arguments, and permissions."""

from collections import defaultdict, deque
from typing import Dict, List, Optional, Set

from sde6_voicebot.contracts.workflow import WorkflowPlan, WorkflowStep
from sde6_voicebot.workflow.exceptions import (
    InvalidPlanError,
    PermissionScopeError,
    ToolArgumentError,
    ToolSecurityError,
)
from sde6_voicebot.workflow.tools import ToolRegistry


class PlanValidator:
    """Validator for WorkflowPlan structures, dependency graphs, tool allow-lists, arguments, and scopes."""

    @classmethod
    def validate_structure_and_dependencies(cls, plan: WorkflowPlan) -> List[str]:
        """Validate step definitions, IDs, referential integrity, and graph acyclicity.
        
        Returns:
            List[str]: Topologically sorted step IDs indicating valid linear execution order.
            
        Raises:
            InvalidPlanError: If steps are empty, IDs are duplicate/blank, dependencies are missing, or cycles exist.
        """
        if not plan.steps:
            raise InvalidPlanError("WorkflowPlan must contain at least one step", correlation_id=plan.correlation_id)

        step_ids: Set[str] = set()
        for idx, step in enumerate(plan.steps):
            if not step.step_id or not step.step_id.strip():
                raise InvalidPlanError(f"Step at index {idx} has a blank step_id", correlation_id=plan.correlation_id)
            if step.step_id in step_ids:
                raise InvalidPlanError(
                    f"Duplicate step_id detected: '{step.step_id}' in plan '{plan.plan_id}'",
                    correlation_id=plan.correlation_id,
                )
            step_ids.add(step.step_id)

        # Validate referential integrity of dependencies
        for step in plan.steps:
            for dep in step.depends_on:
                if dep == step.step_id:
                    raise InvalidPlanError(
                        f"Step '{step.step_id}' cannot depend on itself (self-dependency)",
                        correlation_id=plan.correlation_id,
                    )
                if dep not in step_ids:
                    raise InvalidPlanError(
                        f"Step '{step.step_id}' depends on non-existent step '{dep}'",
                        correlation_id=plan.correlation_id,
                    )

        # Cycle detection and topological sort via Kahn's algorithm
        in_degree: Dict[str, int] = {s.step_id: 0 for s in plan.steps}
        adj: Dict[str, List[str]] = defaultdict(list)

        for step in plan.steps:
            for dep in step.depends_on:
                adj[dep].append(step.step_id)
                in_degree[step.step_id] += 1

        queue: deque[str] = deque([s_id for s_id, deg in in_degree.items() if deg == 0])
        sorted_order: List[str] = []

        while queue:
            curr = queue.popleft()
            sorted_order.append(curr)
            for neighbor in adj[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(sorted_order) != len(plan.steps):
            cyclic_steps = sorted([s_id for s_id, deg in in_degree.items() if deg > 0])
            cycle_paths = cls.trace_cycles(plan.steps, cyclic_steps)
            raise InvalidPlanError(
                f"Cyclic dependency detected among steps: {cyclic_steps}. "
                f"Identified cycle path(s): {cycle_paths}",
                correlation_id=plan.correlation_id,
            )

        return sorted_order

    @classmethod
    def trace_cycles(cls, steps: List[WorkflowStep], cycle_step_ids: List[str]) -> List[List[str]]:
        """Identify explicit cycle paths for clear diagnostic error reporting."""
        step_map = {s.step_id: s for s in steps if s.step_id in cycle_step_ids}
        cycles = []
        visited = set()

        def dfs(node: str, path: List[str]):
            if node in path:
                cycle_slice = path[path.index(node):] + [node]
                cycles.append(cycle_slice)
                return
            if node in visited or node not in step_map:
                return
            visited.add(node)
            for dep in step_map[node].depends_on:
                if dep in cycle_step_ids:
                    dfs(dep, path + [node])

        for s_id in cycle_step_ids:
            dfs(s_id, [])

        return cycles or [[s] for s in cycle_step_ids]

    @classmethod
    def validate_tools_and_arguments(
        cls,
        plan: WorkflowPlan,
        tool_registry: ToolRegistry,
        enforce_arguments: bool = True,
    ) -> None:
        """Validate that all tools referenced in the plan are allow-listed and arguments conform to schema.
        
        Raises:
            ToolSecurityError: If an unknown or disallowed tool is referenced.
            ToolArgumentError: If arguments fail parameter schema validation.
        """
        for step in plan.steps:
            if not tool_registry.has_tool(step.tool_name):
                raise ToolSecurityError(
                    f"Plan contains non-allowlisted tool '{step.tool_name}' in step '{step.step_id}'. "
                    f"Only allowed mock tools {list(tool_registry.ALLOWED_TOOL_NAMES)} are permitted.",
                    tool_name=step.tool_name,
                    correlation_id=plan.correlation_id,
                )
            if enforce_arguments:
                tool_registry.validate_arguments(step.tool_name, step.arguments)

    @classmethod
    def validate_permissions(
        cls,
        plan: WorkflowPlan,
        tool_registry: ToolRegistry,
        granted_scopes: Optional[Set[str]] = None,
    ) -> None:
        """Validate that the execution context possesses required permission scopes for all tools in plan.
        
        Raises:
            PermissionScopeError: If caller lacks required permission scope.
        """
        for step in plan.steps:
            tool_registry.enforce_permission(
                step.tool_name,
                granted_scopes=granted_scopes,
                correlation_id=plan.correlation_id,
            )

    @classmethod
    def validate(
        cls,
        plan: WorkflowPlan,
        tool_registry: Optional[ToolRegistry] = None,
        granted_scopes: Optional[Set[str]] = None,
        enforce_arguments: bool = True,
    ) -> List[str]:
        """Run all plan validations: structure, dependencies, cycles, allow-list, arguments, and permissions.
        
        Returns:
            List[str]: Topologically sorted step order.
        """
        sorted_order = cls.validate_structure_and_dependencies(plan)

        if tool_registry is not None:
            cls.validate_tools_and_arguments(plan, tool_registry, enforce_arguments=enforce_arguments)
            cls.validate_permissions(plan, tool_registry, granted_scopes=granted_scopes)

        return sorted_order
