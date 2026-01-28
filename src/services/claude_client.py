"""Claude (Anthropic) API wrapper with retry logic."""

import logging
import time
from typing import Optional
import anthropic

import sys
sys.path.insert(0, '/home/user/security')
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, CLAUDE_MAX_TOKENS, MAX_RETRIES, RETRY_DELAY_SECONDS

logger = logging.getLogger(__name__)


class ClaudeClient:
    """Wrapper for Anthropic Claude API with retry logic and error handling."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """Initialize the Claude client.

        Args:
            api_key: Anthropic API key (uses env var if not provided)
            model: Model to use (defaults to config setting)
        """
        self.api_key = api_key or ANTHROPIC_API_KEY
        self.model = model or CLAUDE_MODEL
        self.max_tokens = CLAUDE_MAX_TOKENS

        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY is required")

        self.client = anthropic.Anthropic(api_key=self.api_key)

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7
    ) -> str:
        """Generate a response from Claude.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature

        Returns:
            Generated text response

        Raises:
            Exception: If all retries fail
        """
        max_tokens = max_tokens or self.max_tokens
        last_exception = None

        for attempt in range(MAX_RETRIES):
            try:
                messages = [{"role": "user", "content": prompt}]

                kwargs = {
                    "model": self.model,
                    "max_tokens": max_tokens,
                    "messages": messages,
                    "temperature": temperature,
                }

                if system_prompt:
                    kwargs["system"] = system_prompt

                response = self.client.messages.create(**kwargs)
                return response.content[0].text

            except anthropic.RateLimitError as e:
                last_exception = e
                wait_time = RETRY_DELAY_SECONDS * (2 ** attempt)
                logger.warning(f"Rate limited, waiting {wait_time}s (attempt {attempt + 1}/{MAX_RETRIES})")
                time.sleep(wait_time)

            except anthropic.APIError as e:
                last_exception = e
                if attempt < MAX_RETRIES - 1:
                    wait_time = RETRY_DELAY_SECONDS * (2 ** attempt)
                    logger.warning(f"API error: {e}, retrying in {wait_time}s")
                    time.sleep(wait_time)
                else:
                    raise

            except Exception as e:
                logger.error(f"Unexpected error calling Claude: {e}")
                raise

        raise last_exception or Exception("Max retries exceeded")

    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3
    ) -> str:
        """Generate a JSON response from Claude.

        Uses lower temperature for more deterministic output.

        Args:
            prompt: User prompt requesting JSON
            system_prompt: Optional system prompt
            temperature: Sampling temperature (default lower for JSON)

        Returns:
            Generated text (should be parsed as JSON by caller)
        """
        json_system = (system_prompt or "") + "\n\nIMPORTANT: Respond ONLY with valid JSON. No explanations or markdown formatting."
        return self.generate(
            prompt=prompt,
            system_prompt=json_system.strip(),
            temperature=temperature
        )

    def critique(
        self,
        content: str,
        criteria: str,
        context: Optional[str] = None
    ) -> str:
        """Generate a critique of content against criteria.

        Args:
            content: Content to critique
            criteria: Criteria to evaluate against
            context: Optional additional context

        Returns:
            Critique response
        """
        system_prompt = """You are a security expert and code reviewer.
Your task is to critically evaluate content against specific criteria.
Be thorough but fair. Focus on actionable feedback."""

        prompt = f"""Please critique the following content:

{content}

---

Evaluation Criteria:
{criteria}

"""
        if context:
            prompt += f"""
Additional Context:
{context}
"""

        prompt += """
Provide your critique in JSON format with:
- issues: List of problems found
- severity: "critical", "important", or "minor" for each
- suggestions: Specific improvements for each issue

Return ONLY the JSON response."""

        return self.generate(prompt=prompt, system_prompt=system_prompt, temperature=0.4)
