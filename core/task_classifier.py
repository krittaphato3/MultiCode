"""
Task Classifier for MultiCode.

Uses AI to classify tasks as simple or complex, determining whether to:
1. Answer directly (simple tasks like creating a single file, answering questions)
2. Use multi-agent workflow (complex tasks like building projects, multi-file work)
"""

import logging
from typing import Literal

from api.openrouter import ChatMessage, OpenRouterClient

logger = logging.getLogger(__name__)


TaskComplexity = Literal["simple", "complex"]


CLASSIFICATION_PROMPT = """You are a task classifier for MultiCode, an AI coding assistant.

Classify the following user request as either "simple" or "complex".

**SIMPLE tasks** (answer directly):
- Creating a single file (HTML, CSS, JS, Python, etc.)
- Answering questions (math, facts, explanations)
- Simple calculations or conversions
- Writing a short function or script (< 50 lines)
- Explaining code or concepts
- Debugging a small issue
- Generating text content (emails, messages, etc.)

**COMPLEX tasks** (use multi-agent workflow):
- Building multi-file projects
- Creating full applications (web apps, CLI tools, etc.)
- Tasks requiring multiple steps or components
- Projects needing planning, architecture, or design
- Tasks that will create 2+ files
- Anything requiring testing, review, or multiple iterations

**Examples:**
- "Create a login page" → simple (single HTML file)
- "Build a web scraper" → complex (multiple files, logic)
- "What is 15 * 23?" → simple (calculation)
- "Create a Python calculator" → complex (multiple operations, testing)
- "Write a function to sort a list" → simple (single function)
- "Build a REST API with authentication" → complex (multiple endpoints, security)

User request: "{user_input}"

Respond with ONLY one word: "simple" or "complex"."""


async def classify_task(
    client: OpenRouterClient,
    user_input: str,
    model_id: str,
) -> TaskComplexity:
    """
    Classify a task as simple or complex using AI.
    
    Args:
        client: OpenRouter client
        user_input: User's request
        model_id: Model to use for classification
        
    Returns:
        "simple" or "complex"
    """
    try:
        prompt = CLASSIFICATION_PROMPT.format(user_input=user_input)
        
        response = await client.chat_completion(
            messages=[ChatMessage(role="user", content=prompt)],
            model=model_id,
            temperature=0.0,  # Deterministic for classification
            max_tokens=10,
        )
        
        result = response.content.strip().lower()
        
        # Extract classification from response
        if "complex" in result:
            return "complex"
        elif "simple" in result:
            return "simple"
        else:
            # Default to complex if unsure (safer)
            logger.warning(f"Unclassifiable response: {result}, defaulting to complex")
            return "complex"
            
    except Exception as e:
        logger.error(f"Task classification failed: {e}, defaulting to complex")
        return "complex"


def is_simple_task_quick(user_input: str) -> bool:
    """
    Quick heuristic-based check for simple tasks.

    This is a fast pre-filter before AI classification.

    Args:
        user_input: User's request

    Returns:
        True if likely simple, False if likely complex
    """
    user_lower = user_input.lower()

    # Definitely complex patterns (check FIRST)
    complex_patterns = [
        "build a", "create a project", "make an app",
        "web application", "web app", "full stack",
        "multi-file", "multiple files",
        "rest api", "api with", "authentication",
        "database", "with testing", "with tests",
        "complete", "full-featured", "production-ready",
        "and ", " with ",  # Multiple components
        "frontend", "backend", "deploy",
    ]

    # Check for complex patterns first
    for pattern in complex_patterns:
        if pattern in user_lower:
            return False

    # Definitely simple patterns
    simple_patterns = [
        "what is", "what's", "who is", "who's", "when is", "where is",
        "how do i", "how to", "explain", "define",
        "calculate", "what's", "whats",
        "write a function", "write a short",
        "debug this", "fix this error",
        "convert", "translate this",
    ]

    # Check for simple patterns
    for pattern in simple_patterns:
        if pattern in user_lower:
            return True

    # Check if it's a greeting
    if any(greeting in user_lower for greeting in ["hello", "hi", "hey", "good morning", "good afternoon"]):
        return True

    # Check for single-file creation (but NOT with multiple components)
    if "create a" in user_lower or "make a" in user_lower:
        # If it mentions multiple features/components, it's complex
        component_words = ["and", "with", "plus", "including", "featuring"]
        if any(word in user_lower for word in component_words):
            return False

        # Single file type mention is likely simple
        single_file_types = ["html", "css", "js", "javascript", "python file", "py file", "txt file", "md file", "json file", "yaml file"]
        for file_type in single_file_types:
            if file_type in user_lower:
                return True

        # "create a calculator" or similar single-purpose tool
        single_tools = ["calculator", "converter", "timer", "counter", "sorter", "parser"]
        if any(tool in user_lower for tool in single_tools):
            return True

    # Short inputs (under 5 words) are usually simple
    word_count = len(user_input.split())
    if word_count <= 4:
        return True

    # Default to complex for safety
    return False
