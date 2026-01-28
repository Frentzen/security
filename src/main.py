"""Main entry point for the security research agent."""

import argparse
import json
import logging
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agent.graph import run_agent
from config import LOG_LEVEL

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)


def load_input_from_file(file_path: str) -> dict:
    """Load input configuration from JSON file.

    Args:
        file_path: Path to JSON file

    Returns:
        Input context dictionary
    """
    with open(file_path, 'r') as f:
        return json.load(f)


def save_report(report: str, output_path: str) -> None:
    """Save the generated report to a file.

    Args:
        report: Markdown report content
        output_path: Path to output file
    """
    with open(output_path, 'w') as f:
        f.write(report)
    logger.info(f"Report saved to: {output_path}")


def create_default_output_path(context: dict) -> str:
    """Create a default output file path based on context.

    Args:
        context: Input context

    Returns:
        Default output file path
    """
    topic = context.get("security_topic", "security").replace(" ", "_").lower()
    backend = context.get("tech_stack", {}).get("backend", "generic").replace(" ", "_").lower()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"output/{topic}_{backend}_{timestamp}.md"


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Security Research Agent - Generate security implementation guides"
    )

    parser.add_argument(
        "-i", "--input",
        type=str,
        help="Path to JSON input file"
    )

    parser.add_argument(
        "-o", "--output",
        type=str,
        help="Path to output markdown file"
    )

    parser.add_argument(
        "--project-type",
        type=str,
        choices=["api_only", "fullstack_app", "opensource_project", "microservice"],
        help="Type of project"
    )

    parser.add_argument(
        "--backend",
        type=str,
        help="Backend framework (e.g., FastAPI, Django, Spring Boot)"
    )

    parser.add_argument(
        "--frontend",
        type=str,
        help="Frontend framework (e.g., React, Vue, Angular)"
    )

    parser.add_argument(
        "--database",
        type=str,
        help="Database (e.g., PostgreSQL, MongoDB, MySQL)"
    )

    parser.add_argument(
        "--deployment",
        type=str,
        help="Deployment target (e.g., Docker, Kubernetes, AWS)"
    )

    parser.add_argument(
        "--topic",
        type=str,
        help="Security topic (e.g., 'JWT Authentication', 'API Rate Limiting')"
    )

    parser.add_argument(
        "--project-url",
        type=str,
        help="Project URL for OSS analysis"
    )

    parser.add_argument(
        "--project-name",
        type=str,
        help="Project name for OSS analysis"
    )

    parser.add_argument(
        "-q", "--query",
        type=str,
        help="Natural language query describing your security need (e.g., 'I need to implement JWE encryption in my Spring Boot microservices deployed on AKS')"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Set verbose logging if requested
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Build input context
    if args.input:
        # Load from file
        logger.info(f"Loading input from: {args.input}")
        context = load_input_from_file(args.input)
    elif args.query:
        # Natural language query mode
        logger.info("Using natural language query mode")
        context = {
            "raw_query": args.query,
            "tech_stack": {},
        }

        # Allow overriding specific fields alongside the query
        if args.project_type:
            context["project_type"] = args.project_type
        if args.backend:
            context.setdefault("tech_stack", {})["backend"] = args.backend
        if args.frontend:
            context.setdefault("tech_stack", {})["frontend"] = args.frontend
        if args.database:
            context.setdefault("tech_stack", {})["database"] = args.database
        if args.deployment:
            context.setdefault("tech_stack", {})["deployment"] = args.deployment
        if args.project_url:
            context["project_url"] = args.project_url
        if args.project_name:
            context["project_name"] = args.project_name
        if args.topic:
            context["security_topic"] = args.topic
    else:
        # Build from command line arguments
        if not args.topic:
            parser.error("--topic or --query is required when not using --input")

        context = {
            "project_type": args.project_type or "api_only",
            "security_topic": args.topic,
            "tech_stack": {},
        }

        if args.backend:
            context["tech_stack"]["backend"] = args.backend
        if args.frontend:
            context["tech_stack"]["frontend"] = args.frontend
        if args.database:
            context["tech_stack"]["database"] = args.database
        if args.deployment:
            context["tech_stack"]["deployment"] = args.deployment
        if args.project_url:
            context["project_url"] = args.project_url
        if args.project_name:
            context["project_name"] = args.project_name

    # Validate: need either security_topic or raw_query
    if not context.get("security_topic") and not context.get("raw_query"):
        logger.error("Either --topic or --query is required")
        sys.exit(1)

    if context.get("raw_query"):
        logger.info(f"Starting agent with query: {context['raw_query'][:80]}...")
    else:
        logger.info(f"Starting agent for: {context.get('security_topic')}")
        logger.info(f"Tech stack: {context.get('tech_stack', {})}")

    # Run the agent
    try:
        report = run_agent(context)

        # Determine output path
        output_path = args.output
        if not output_path:
            output_path = create_default_output_path(context)

        # Ensure output directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # Save the report
        save_report(report, output_path)

        print(f"\n{'='*60}")
        print(f"Report generated successfully!")
        print(f"Output: {output_path}")
        print(f"{'='*60}\n")

        # Also print a preview
        preview_lines = report.split('\n')[:20]
        print("Preview:")
        print('\n'.join(preview_lines))
        if len(report.split('\n')) > 20:
            print("...")
            print(f"\n[Full report saved to {output_path}]")

    except Exception as e:
        logger.exception(f"Agent failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
