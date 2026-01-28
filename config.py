"""Configuration settings for the security research agent."""

import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# Model settings
CLAUDE_MODEL = "claude-sonnet-4-20250514"
CLAUDE_MAX_TOKENS = 8192

# Agent settings
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "3"))
MAX_SEARCH_RESULTS_PER_QUERY = 5
MAX_RESEARCH_QUESTIONS = 7

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Retry settings
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2
