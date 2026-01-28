"""State definition for the security research agent."""

from typing import TypedDict, Optional, Literal, NotRequired


class TechStack(TypedDict, total=False):
    """Technology stack configuration."""
    backend: str
    frontend: Optional[str]
    database: Optional[str]
    deployment: Optional[str]


class InputContext(TypedDict, total=False):
    """Input context from user."""
    project_type: Literal["api_only", "fullstack_app", "opensource_project", "microservice"]
    project_name: Optional[str]
    project_url: Optional[str]
    tech_stack: TechStack
    security_topic: str
    requirements: Optional[dict]
    raw_query: Optional[str]


class SearchResult(TypedDict):
    """Individual search result."""
    query: str
    url: str
    title: str
    snippet: str
    score: NotRequired[float]


class ValidationIssue(TypedDict):
    """Validation issue from critic."""
    issue: str
    severity: Literal["critical", "important", "minor"]
    suggestion: str


class RepositoryAnalysis(TypedDict, total=False):
    """Repository analysis results."""
    languages: list[str]
    frameworks: list[str]
    build_tools: list[str]
    security_configs: list[str]
    architecture_patterns: list[str]
    readme_summary: str
    detected_tech_stack: TechStack


class SynthesizedKnowledge(TypedDict, total=False):
    """Organized research findings."""
    prerequisites: list[str]
    implementation_steps: list[dict]
    security_best_practices: list[str]
    code_patterns: list[dict]
    configuration_requirements: list[str]
    deployment_considerations: list[str]
    common_pitfalls: list[str]
    authoritative_sources: list[dict]


class AgentState(TypedDict, total=False):
    """Complete state for the security research agent."""

    # Input fields
    context: InputContext

    # Discovery fields (for OSS projects)
    needs_discovery: bool
    repository_analysis: Optional[RepositoryAnalysis]

    # Research fields
    research_plan: list[str]
    search_results: list[SearchResult]
    synthesized_knowledge: Optional[SynthesizedKnowledge]

    # Generation fields
    architecture_draft: str
    validation_feedback: list[ValidationIssue]

    # Output fields
    final_report: str

    # Control fields
    iteration_count: int
    needs_query_parsing: bool

    # Error tracking
    errors: list[str]
