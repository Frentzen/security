"""Node implementations for the security research agent."""

import logging
import json
from typing import Any

import sys
sys.path.insert(0, '/home/user/security')

from src.agent.state import AgentState, SearchResult, ValidationIssue, SynthesizedKnowledge
from src.services.claude_client import ClaudeClient
from src.services.tavily_client import TavilyClient
from src.utils.helpers import extract_json_from_response, format_search_results, sanitize_markdown, merge_tech_stacks
from config import MAX_RESEARCH_QUESTIONS, MAX_ITERATIONS

logger = logging.getLogger(__name__)

# Initialize clients
claude = ClaudeClient()
tavily = TavilyClient()


def query_parser(state: AgentState) -> dict[str, Any]:
    """Parse a natural language query to extract structured context.

    Uses Claude to understand the user's intent and extract project type,
    tech stack, security topic, and additional requirements from free-form text.

    Args:
        state: Current agent state

    Returns:
        Updated state with parsed context
    """
    logger.info("Parsing natural language query")

    context = state.get("context", {})
    raw_query = context.get("raw_query", "")

    if not raw_query:
        logger.warning("No raw query to parse")
        return {"needs_query_parsing": False}

    prompt = f"""Analyze the following user request about a security implementation need and extract structured information.

User Request:
"{raw_query}"

Extract and return a JSON object with these fields:
{{
    "security_topic": "The main security topic (e.g., 'JWE Payload Encryption', 'JWT Authentication', 'OAuth2', 'API Rate Limiting', 'mTLS', 'CSRF Protection')",
    "project_type": "One of: api_only, fullstack_app, opensource_project, microservice",
    "tech_stack": {{
        "backend": "Backend framework or language (e.g., 'Spring Boot', 'FastAPI', 'Django', 'Express.js') or null",
        "frontend": "Frontend framework (e.g., 'React', 'Angular', 'Vue') or null",
        "database": "Database (e.g., 'PostgreSQL', 'MongoDB', 'MySQL') or null",
        "deployment": "Deployment platform/tools (e.g., 'AKS', 'Kubernetes', 'Docker', 'AWS ECS') or null"
    }},
    "project_name": "Project name if mentioned, or null",
    "project_url": "Repository URL if mentioned, or null",
    "requirements": {{
        "additional_context": "Any extra details from the query that don't fit the fields above (cloud provider, API gateway, specific services, compliance needs, etc.)",
        "cloud_provider": "Cloud provider if mentioned (e.g., 'Azure', 'AWS', 'GCP') or null",
        "infrastructure_components": ["List of infrastructure components mentioned (e.g., 'APIM', 'Application Gateway', 'API Gateway', 'Load Balancer')"]
    }}
}}

Rules:
- Extract as much as possible from the query; use null for anything not mentioned
- For project_type, infer from context: if they mention microservices use "microservice", if they mention frontend use "fullstack_app", otherwise default to "api_only"
- For security_topic, be specific and descriptive (e.g., "JWE JSON Payload Encryption" not just "encryption")
- For deployment, include the orchestration platform (e.g., "AKS" not just "Kubernetes") if specified
- Capture cloud-specific services (like Azure APIM, AWS API Gateway) in requirements.infrastructure_components
- If the user mentions a specific standard or RFC, include it in requirements.additional_context

Return ONLY valid JSON."""

    try:
        response = claude.generate_json(prompt)
        parsed = extract_json_from_response(response)

        # Build the updated context, preserving any fields already set by the user
        updated_context = {**context}

        # Set security_topic (always from parsed result since it's derived from query)
        if parsed.get("security_topic"):
            updated_context["security_topic"] = parsed["security_topic"]

        # Set project_type (user-provided takes precedence)
        if not context.get("project_type") and parsed.get("project_type"):
            updated_context["project_type"] = parsed["project_type"]

        # Merge tech stacks: user-provided values take precedence
        user_stack = context.get("tech_stack", {})
        parsed_stack = parsed.get("tech_stack", {})
        merged_stack = {}
        for key in ("backend", "frontend", "database", "deployment"):
            user_val = user_stack.get(key)
            parsed_val = parsed_stack.get(key)
            if user_val:
                merged_stack[key] = user_val
            elif parsed_val:
                merged_stack[key] = parsed_val
        updated_context["tech_stack"] = merged_stack

        # Set optional fields
        if not context.get("project_name") and parsed.get("project_name"):
            updated_context["project_name"] = parsed["project_name"]
        if not context.get("project_url") and parsed.get("project_url"):
            updated_context["project_url"] = parsed["project_url"]

        # Merge requirements
        user_reqs = context.get("requirements") or {}
        parsed_reqs = parsed.get("requirements") or {}
        if parsed_reqs or user_reqs:
            updated_context["requirements"] = {**parsed_reqs, **user_reqs}

        logger.info(
            f"Query parsed - Topic: {updated_context.get('security_topic')}, "
            f"Type: {updated_context.get('project_type')}, "
            f"Stack: {updated_context.get('tech_stack')}"
        )

        return {
            "context": updated_context,
            "needs_query_parsing": False,
        }

    except Exception as e:
        logger.error(f"Query parsing failed: {e}")
        return {
            "errors": state.get("errors", []) + [f"Query parsing failed: {str(e)}"],
            "needs_query_parsing": False,
        }


def context_analyzer(state: AgentState) -> dict[str, Any]:
    """Analyze input context and determine workflow path.

    Checks if tech stack is complete and if OSS discovery is needed.

    Args:
        state: Current agent state

    Returns:
        Updated state fields
    """
    logger.info("Analyzing input context")

    context = state.get("context", {})
    project_type = context.get("project_type", "api_only")
    project_url = context.get("project_url")
    tech_stack = context.get("tech_stack", {})

    # Determine if discovery is needed
    needs_discovery = False

    # For OSS projects with URL but incomplete tech stack
    if project_type == "opensource_project" and project_url:
        if not tech_stack.get("backend"):
            needs_discovery = True
            logger.info(f"Discovery needed for OSS project: {project_url}")

    # Initialize iteration count if not set
    iteration_count = state.get("iteration_count", 0)

    return {
        "needs_discovery": needs_discovery,
        "iteration_count": iteration_count,
        "errors": state.get("errors", []),
    }


def repository_analyzer(state: AgentState) -> dict[str, Any]:
    """Analyze open-source repository to extract information.

    Uses Tavily to search for repository documentation and README.

    Args:
        state: Current agent state

    Returns:
        Updated state with repository_analysis
    """
    logger.info("Analyzing repository")

    context = state.get("context", {})
    project_url = context.get("project_url", "")
    project_name = context.get("project_name", "")

    # Build search query
    if project_url:
        search_query = f"{project_url} README documentation tech stack"
    elif project_name:
        search_query = f"{project_name} github README documentation"
    else:
        logger.warning("No project URL or name provided for repository analysis")
        return {"repository_analysis": None}

    try:
        # Search for repository information
        results = tavily.search(search_query, max_results=5)

        # Also search for specific tech files
        tech_query = f"{project_name or project_url} package.json requirements.txt pom.xml build.gradle"
        tech_results = tavily.search(tech_query, max_results=3)
        results.extend(tech_results)

        if not results:
            logger.warning("No repository information found")
            return {"repository_analysis": None}

        # Use Claude to analyze the results
        results_text = format_search_results(results)

        prompt = f"""Analyze the following search results about a software project and extract technology stack information.

Search Results:
{results_text}

Extract and return a JSON object with:
- languages: List of programming languages used
- frameworks: List of frameworks detected (backend and frontend)
- build_tools: List of build tools (npm, maven, gradle, pip, etc.)
- security_configs: Any security configurations mentioned
- architecture_patterns: Detected architecture patterns
- readme_summary: Brief summary of the project
- detected_tech_stack: Object with backend, frontend, database, deployment fields

Return ONLY valid JSON."""

        response = claude.generate_json(prompt)
        analysis = extract_json_from_response(response)

        logger.info(f"Repository analysis complete: {analysis.get('detected_tech_stack', {})}")
        return {"repository_analysis": analysis}

    except Exception as e:
        logger.error(f"Repository analysis failed: {e}")
        return {
            "repository_analysis": None,
            "errors": state.get("errors", []) + [f"Repository analysis failed: {str(e)}"]
        }


def tech_stack_discovery(state: AgentState) -> dict[str, Any]:
    """Extract complete tech stack from repository analysis.

    Merges discovered tech stack with user-provided context.

    Args:
        state: Current agent state

    Returns:
        Updated state with merged tech stack
    """
    logger.info("Discovering tech stack")

    context = state.get("context", {})
    repository_analysis = state.get("repository_analysis")

    if not repository_analysis:
        logger.warning("No repository analysis available for tech stack discovery")
        return {}

    user_tech_stack = context.get("tech_stack", {})
    discovered_stack = repository_analysis.get("detected_tech_stack", {})

    # Merge tech stacks (user-provided takes precedence)
    merged_stack = merge_tech_stacks(user_tech_stack, discovered_stack)

    # Update context with merged tech stack
    updated_context = {**context, "tech_stack": merged_stack}

    logger.info(f"Tech stack discovered: {merged_stack}")
    return {
        "context": updated_context,
        "needs_discovery": False,  # Discovery complete
    }


def planner(state: AgentState) -> dict[str, Any]:
    """Create research plan based on context.

    Generates list of specific research questions.

    Args:
        state: Current agent state

    Returns:
        Updated state with research_plan
    """
    logger.info("Creating research plan")

    context = state.get("context", {})
    security_topic = context.get("security_topic", "")
    project_type = context.get("project_type", "api_only")
    tech_stack = context.get("tech_stack", {})

    backend = tech_stack.get("backend", "")
    frontend = tech_stack.get("frontend", "")
    database = tech_stack.get("database", "")
    deployment = tech_stack.get("deployment", "")

    prompt = f"""Create a research plan for implementing secure {security_topic} in a {project_type} project.

Tech Stack:
- Backend: {backend or 'Not specified'}
- Frontend: {frontend or 'Not specified'}
- Database: {database or 'Not specified'}
- Deployment: {deployment or 'Not specified'}

Generate {MAX_RESEARCH_QUESTIONS} specific research questions that will help gather:
1. Best practices and standards (OWASP, RFCs, NIST)
2. Framework-specific implementation guidance for {backend}
3. Common vulnerabilities and mitigations for {security_topic}
4. Code examples and configurations
5. Deployment and production considerations

Return ONLY a JSON array of search queries optimized for web search. Make them specific and actionable.
Example format: ["query 1", "query 2", ...]"""

    try:
        response = claude.generate_json(prompt)
        research_plan = extract_json_from_response(response)

        if not isinstance(research_plan, list):
            research_plan = [research_plan]

        # Ensure we have valid queries
        research_plan = [q for q in research_plan if isinstance(q, str) and len(q) > 5]

        # Add some standard security queries
        if backend:
            research_plan.append(f"{security_topic} {backend} implementation tutorial")
        research_plan.append(f"OWASP {security_topic} best practices")

        # Limit to max questions
        research_plan = research_plan[:MAX_RESEARCH_QUESTIONS]

        logger.info(f"Research plan created with {len(research_plan)} questions")
        return {"research_plan": research_plan}

    except Exception as e:
        logger.error(f"Planning failed: {e}")
        # Fallback to basic research plan
        fallback_plan = [
            f"{security_topic} best practices OWASP",
            f"{security_topic} implementation guide",
            f"{security_topic} {backend} tutorial" if backend else f"{security_topic} tutorial",
            f"{security_topic} security vulnerabilities",
            f"{security_topic} production configuration",
        ]
        return {
            "research_plan": fallback_plan,
            "errors": state.get("errors", []) + [f"Planning error (using fallback): {str(e)}"]
        }


def researcher(state: AgentState) -> dict[str, Any]:
    """Execute searches and gather information.

    Runs research queries via Tavily and collects results.

    Args:
        state: Current agent state

    Returns:
        Updated state with search_results
    """
    logger.info("Executing research queries")

    research_plan = state.get("research_plan", [])

    if not research_plan:
        logger.warning("No research plan available")
        return {"search_results": []}

    try:
        # Execute searches in parallel
        all_results = tavily.search_parallel(research_plan)

        # Deduplicate by URL
        seen_urls = set()
        unique_results = []
        for result in all_results:
            url = result.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(result)

        logger.info(f"Research complete: {len(unique_results)} unique results from {len(research_plan)} queries")
        return {"search_results": unique_results}

    except Exception as e:
        logger.error(f"Research failed: {e}")
        return {
            "search_results": [],
            "errors": state.get("errors", []) + [f"Research failed: {str(e)}"]
        }


def synthesizer(state: AgentState) -> dict[str, Any]:
    """Organize and structure research findings.

    Groups information by topic and extracts key insights.

    Args:
        state: Current agent state

    Returns:
        Updated state with synthesized_knowledge
    """
    logger.info("Synthesizing research findings")

    search_results = state.get("search_results", [])
    context = state.get("context", {})
    security_topic = context.get("security_topic", "")
    tech_stack = context.get("tech_stack", {})

    if not search_results:
        logger.warning("No search results to synthesize")
        return {"synthesized_knowledge": None}

    results_text = format_search_results(search_results)

    prompt = f"""Analyze and organize the following security research results for implementing {security_topic}.

Target Tech Stack:
- Backend: {tech_stack.get('backend', 'Not specified')}
- Frontend: {tech_stack.get('frontend', 'Not specified')}
- Database: {tech_stack.get('database', 'Not specified')}
- Deployment: {tech_stack.get('deployment', 'Not specified')}

Research Results:
{results_text}

Organize these findings into a JSON object with the following structure:
{{
    "prerequisites": ["list of dependencies and setup requirements"],
    "implementation_steps": [
        {{"step": "step description", "details": "specific implementation details", "source": "URL if available"}}
    ],
    "security_best_practices": ["list of security best practices with sources"],
    "code_patterns": [
        {{"pattern": "pattern name", "description": "what it does", "when_to_use": "context"}}
    ],
    "configuration_requirements": ["list of configuration settings needed"],
    "deployment_considerations": ["list of deployment and production considerations"],
    "common_pitfalls": ["list of common mistakes to avoid"],
    "authoritative_sources": [
        {{"title": "source title", "url": "source URL", "relevance": "why it's relevant"}}
    ]
}}

Focus on actionable, practical information. Prioritize recommendations from OWASP, RFCs, and official documentation.
Return ONLY valid JSON."""

    try:
        response = claude.generate_json(prompt)
        knowledge = extract_json_from_response(response)

        logger.info("Research synthesis complete")
        return {"synthesized_knowledge": knowledge}

    except Exception as e:
        logger.error(f"Synthesis failed: {e}")
        return {
            "synthesized_knowledge": None,
            "errors": state.get("errors", []) + [f"Synthesis failed: {str(e)}"]
        }


def architect(state: AgentState) -> dict[str, Any]:
    """Generate implementation guide draft.

    Creates markdown document with code examples and configurations.

    Args:
        state: Current agent state

    Returns:
        Updated state with architecture_draft
    """
    logger.info("Generating implementation guide")

    context = state.get("context", {})
    synthesized_knowledge = state.get("synthesized_knowledge")
    search_results = state.get("search_results", [])

    security_topic = context.get("security_topic", "")
    project_type = context.get("project_type", "api_only")
    tech_stack = context.get("tech_stack", {})

    backend = tech_stack.get("backend", "")
    frontend = tech_stack.get("frontend", "")
    database = tech_stack.get("database", "")
    deployment = tech_stack.get("deployment", "")

    # Format knowledge for prompt
    knowledge_text = json.dumps(synthesized_knowledge, indent=2) if synthesized_knowledge else "No synthesized knowledge available"

    # Format sources for citations
    sources = []
    for result in search_results[:20]:  # Limit sources
        sources.append(f"- {result.get('title', 'Unknown')}: {result.get('url', '')}")
    sources_text = "\n".join(sources) if sources else "No sources available"

    system_prompt = """You are a senior security engineer creating practical implementation guides.
Your guides must be:
- Practical and copy-paste ready
- Include complete, working code examples
- Security-focused with inline comments
- Concise but thorough
- Well-cited with references

Write in markdown format. Use code blocks with language tags.
Do not include architecture diagrams or excessive theory."""

    prompt = f"""Generate a complete implementation guide for developers.

Topic: Implement secure {security_topic}
Project Type: {project_type}
Tech Stack:
- Backend: {backend or 'Generic'}
- Frontend: {frontend or 'N/A'}
- Database: {database or 'N/A'}
- Deployment: {deployment or 'Docker'}

Organized Research Knowledge:
{knowledge_text}

Available Sources for Citations:
{sources_text}

Generate a markdown document with these sections:
1. **Overview** (2-3 sentences max)
2. **Prerequisites** (dependencies, versions, setup)
3. **Implementation Guide**
   - Backend implementation with complete code examples for {backend or 'your framework'}
   {"- Frontend implementation with code for " + frontend if frontend else ""}
   - Configuration files (environment variables, config files)
4. **Deployment**
   - {deployment or 'Docker'} configuration with security best practices
   - Production checklist
5. **Common Issues and Troubleshooting** (3-5 common problems)
6. **Security Notes** (key security considerations, OWASP references)
7. **References** (numbered list with URLs)

Requirements:
- Code must be PRODUCTION-READY, not pseudocode
- Include ALL necessary imports and error handling
- Add inline comments explaining security decisions
- Cite sources using [1], [2] format inline, list at end
- Keep it practical - no excessive theory
- Use realistic variable names and configurations"""

    try:
        draft = claude.generate(prompt, system_prompt=system_prompt, max_tokens=8000)
        draft = sanitize_markdown(draft)

        logger.info(f"Implementation guide draft generated ({len(draft)} chars)")
        return {"architecture_draft": draft}

    except Exception as e:
        logger.error(f"Guide generation failed: {e}")
        return {
            "architecture_draft": "",
            "errors": state.get("errors", []) + [f"Guide generation failed: {str(e)}"]
        }


def validator(state: AgentState) -> dict[str, Any]:
    """Review and critique the implementation guide.

    Checks for security gaps, code completeness, and best practices.

    Args:
        state: Current agent state

    Returns:
        Updated state with validation_feedback
    """
    logger.info("Validating implementation guide")

    architecture_draft = state.get("architecture_draft", "")
    context = state.get("context", {})
    security_topic = context.get("security_topic", "")
    tech_stack = context.get("tech_stack", {})

    if not architecture_draft:
        logger.warning("No draft to validate")
        return {"validation_feedback": []}

    prompt = f"""Review this security implementation guide for quality and completeness.

Implementation Guide:
{architecture_draft}

Tech Stack: {json.dumps(tech_stack)}
Security Topic: {security_topic}

Evaluate against these criteria:
1. Security gaps - Missing security controls, potential vulnerabilities
2. Code completeness - All imports present, error handling, no truncated examples
3. Best practice compliance - OWASP standards, framework conventions
4. Deployment readiness - Configs complete, environment variables documented
5. Citation quality - Sources authoritative and properly cited
6. Practical usefulness - Can a developer actually use this?

Return a JSON object with:
{{
    "issues": [
        {{
            "issue": "Description of the problem",
            "severity": "critical|important|minor",
            "suggestion": "Specific improvement recommendation"
        }}
    ],
    "overall_quality": "good|acceptable|needs_work",
    "missing_sections": ["list of missing important sections"]
}}

Be thorough but fair. Focus on issues that would actually affect a developer using this guide.
Return ONLY valid JSON."""

    try:
        response = claude.generate_json(prompt)
        feedback = extract_json_from_response(response)

        issues = feedback.get("issues", [])

        # Convert to ValidationIssue format
        validation_feedback = []
        for issue in issues:
            validation_feedback.append({
                "issue": issue.get("issue", "Unknown issue"),
                "severity": issue.get("severity", "minor"),
                "suggestion": issue.get("suggestion", ""),
            })

        # Filter to critical and important only for triggering revision
        critical_count = sum(1 for i in validation_feedback if i["severity"] == "critical")
        important_count = sum(1 for i in validation_feedback if i["severity"] == "important")

        logger.info(f"Validation complete: {critical_count} critical, {important_count} important issues")
        return {"validation_feedback": validation_feedback}

    except Exception as e:
        logger.error(f"Validation failed: {e}")
        return {
            "validation_feedback": [],
            "errors": state.get("errors", []) + [f"Validation failed: {str(e)}"]
        }


def revision(state: AgentState) -> dict[str, Any]:
    """Improve guide based on validation feedback.

    Addresses critical and important issues from validation.

    Args:
        state: Current agent state

    Returns:
        Updated state with improved architecture_draft
    """
    logger.info("Revising implementation guide")

    architecture_draft = state.get("architecture_draft", "")
    validation_feedback = state.get("validation_feedback", [])
    iteration_count = state.get("iteration_count", 0)

    if not architecture_draft or not validation_feedback:
        return {"iteration_count": iteration_count + 1}

    # Format feedback for prompt
    feedback_text = []
    for item in validation_feedback:
        if item["severity"] in ["critical", "important"]:
            feedback_text.append(f"- [{item['severity'].upper()}] {item['issue']}\n  Suggestion: {item['suggestion']}")

    if not feedback_text:
        logger.info("No critical/important issues to address")
        return {"iteration_count": iteration_count + 1}

    feedback_formatted = "\n".join(feedback_text)

    prompt = f"""Improve this implementation guide based on the validation feedback.

Current Guide:
{architecture_draft}

Issues to Address:
{feedback_formatted}

Instructions:
1. Address each critical and important issue
2. Preserve existing good content
3. Add missing security controls
4. Improve code examples where needed
5. Ensure all configurations are production-ready
6. Maintain the same structure and format

Return the complete improved guide in markdown format.
Do NOT add explanations before or after - just the improved guide."""

    try:
        improved = claude.generate(prompt, max_tokens=8000)
        improved = sanitize_markdown(improved)

        logger.info(f"Guide revised (iteration {iteration_count + 1})")
        return {
            "architecture_draft": improved,
            "iteration_count": iteration_count + 1,
            "validation_feedback": [],  # Clear feedback after revision
        }

    except Exception as e:
        logger.error(f"Revision failed: {e}")
        return {
            "iteration_count": iteration_count + 1,
            "errors": state.get("errors", []) + [f"Revision failed: {str(e)}"]
        }


def report_generator(state: AgentState) -> dict[str, Any]:
    """Finalize and format the markdown report.

    Applies final formatting and creates the final report.

    Args:
        state: Current agent state

    Returns:
        Updated state with final_report
    """
    logger.info("Generating final report")

    architecture_draft = state.get("architecture_draft", "")
    context = state.get("context", {})
    security_topic = context.get("security_topic", "")
    iteration_count = state.get("iteration_count", 0)

    if not architecture_draft:
        error_report = f"""# {security_topic} Implementation Guide

## Error

Unable to generate implementation guide. Please check the logs for details.

### Input Context
```json
{json.dumps(context, indent=2)}
```

### Errors
{chr(10).join(state.get('errors', ['No specific errors recorded']))}
"""
        return {"final_report": error_report}

    # Clean up the draft
    final_report = sanitize_markdown(architecture_draft)

    # Add metadata footer
    metadata = f"""

---

*Generated by Security Research Agent*
*Iterations: {iteration_count}*
"""

    final_report += metadata

    logger.info(f"Final report generated ({len(final_report)} chars)")
    return {"final_report": final_report}
