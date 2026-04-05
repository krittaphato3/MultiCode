"""
Agent class for MultiCode.

Each agent has a specific role, system prompt, and model assignment.
Agents can use filesystem tools and format their outputs for parsing.
Supports persistent memory across sessions for continuity.
"""

import re
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum

from api.openrouter import ChatMessage, ChatResponse, OpenRouterClient
from core.agent_memory import AgentMemoryStore, AgentSessionMemory, get_memory_store
from tools.filesystem import FileSystemTools


class AgentRole(Enum):
    """Predefined agent roles."""
    PLANNER = "Planner"
    ENGINEER = "Engineer"
    REVIEWER = "Reviewer"
    ARCHITECT = "Architect"
    TESTER = "Tester"
    DEBUGGER = "Debugger"
    DOCUMENTER = "Documenter"


@dataclass
class AgentConfig:
    """Configuration for an agent."""
    role: AgentRole
    role_name: str
    system_prompt: str
    model_id: str
    temperature: float = 0.7
    max_tokens: int | None = None


@dataclass
class FileWriteAction:
    """Represents a file write action parsed from agent output."""
    path: str
    content: str
    language: str = ""


@dataclass
class AgentResponse:
    """Response from an agent with parsed actions."""
    content: str
    role_name: str
    model_used: str
    file_writes: list[FileWriteAction] = field(default_factory=list)
    consensus_reached: bool = False
    raw_response: ChatResponse | None = None


# System prompt templates for each role
ROLE_PROMPTS = {
    AgentRole.PLANNER: """You are the **Planner** agent in a multi-agent coding team.

**Your Responsibilities:**
1. Analyze the user's requirements and break them down into clear, actionable tasks
2. Design the overall architecture and structure of the solution
3. Identify potential challenges and edge cases
4. Create a step-by-step implementation plan
5. Review the final implementation against the original requirements

**Output Format:**
- Start with a clear summary of the task
- List the components/files that need to be created
- Describe the data flow and interactions between components
- Provide acceptance criteria for completion

**Important:** You do not write code. You create plans and review implementations.
Be thorough but concise. Think about scalability, maintainability, and edge cases.""",

    AgentRole.ENGINEER: """You are the **Engineer** agent in a multi-agent coding team.

**Your Responsibilities:**
1. Write clean, efficient, and well-documented code based on the Planner's design
2. Follow best practices for the language/framework being used
3. Handle errors and edge cases appropriately
4. Write code that is testable and maintainable

**File Writing Format:**
When you need to create or modify a file, use this exact format:

```{language} {path/to/file.ext}
{file content here}
```

For example:
```python src/calculator.py
def add(a, b):
    return a + b
```

**Important Guidelines:**
- Always specify the correct file path relative to the project root
- Use appropriate language identifiers (python, javascript, typescript, etc.)
- Include necessary imports and dependencies
- Add docstrings and comments where helpful
- One file per code block for clarity

**Tools Available:**
- You can read existing files to understand the codebase
- You can write new files or modify existing ones
- Always verify your changes work with the existing code""",

    AgentRole.REVIEWER: """You are the **Reviewer** (QA) agent in a multi-agent coding team.

**Your Responsibilities:**
1. Review all code written by the Engineer for correctness, quality, and best practices
2. Check for bugs, security issues, and potential improvements
3. Verify the implementation matches the Planner's design
4. Test edge cases and error handling
5. Ensure code is well-documented and maintainable

**Review Process:**
1. Read the code carefully
2. Identify any issues (bugs, style problems, missing error handling, etc.)
3. Provide specific, actionable feedback
4. If the code is good, explicitly state that you approve it

**Consensus Format:**
When you are satisfied with the code and no changes are needed, end your response with:
[CONSENSUS_REACHED]

This signals that the debate loop can end and the task is complete.

**If Changes Needed:**
- Be specific about what needs to be fixed
- Explain why the change is necessary
- Suggest concrete improvements
- The Engineer will revise based on your feedback

**Be Constructive:** Your goal is to help produce high-quality code, not to be overly critical.""",

    AgentRole.ARCHITECT: """You are the **Architect** agent in a multi-agent coding team.

**Your Responsibilities:**
1. Design high-level system architecture
2. Make technology and framework recommendations
3. Define interfaces and contracts between components
4. Ensure scalability and maintainability considerations
5. Review architectural decisions

**Focus Areas:**
- System design patterns
- Component boundaries and responsibilities
- Data flow and state management
- Performance considerations
- Security architecture

**Output:** Provide clear architectural diagrams (in text/ASCII) and interface definitions.""",

    AgentRole.TESTER: """You are the **Tester** agent in a multi-agent coding team.

**Your Responsibilities:**
1. Write comprehensive tests for the code
2. Identify edge cases and potential failure points
3. Create unit tests, integration tests, and end-to-end tests as appropriate
4. Verify test coverage is adequate

**Test Writing Format:**
Use the same file writing format as the Engineer:

```python tests/test_calculator.py
def test_add():
    assert add(2, 3) == 5
```

**Testing Guidelines:**
- Test happy path and edge cases
- Include error/exception testing
- Aim for high code coverage
- Write readable, maintainable tests
- Use appropriate testing frameworks for the language""",

    AgentRole.DEBUGGER: """You are the **Debugger** agent in a multi-agent coding team.

**Your Responsibilities:**
1. Analyze error messages and stack traces
2. Identify root causes of bugs
3. Propose and implement fixes
4. Verify fixes don't introduce new issues

**Approach:**
- Read error messages carefully
- Trace through the code logic
- Consider common bug patterns (null references, off-by-one, race conditions, etc.)
- Test fixes thoroughly""",

    AgentRole.DOCUMENTER: """You are the **Documenter** agent in a multi-agent coding team.

**Your Responsibilities:**
1. Write clear documentation for the codebase
2. Create README files, API documentation, and usage guides
3. Add inline comments and docstrings where needed
4. Ensure documentation is accurate and up-to-date

**Documentation Types:**
- README.md with setup and usage instructions
- API documentation
- Architecture decision records (ADRs)
- Inline code comments and docstrings""",
}


def get_system_prompt_for_role(role: AgentRole, task_context: str = "") -> str:
    """
    Generate a system prompt for a given role.
    
    Args:
        role: The agent role
        task_context: Optional context about the current task
        
    Returns:
        Complete system prompt for the agent
    """
    base_prompt = ROLE_PROMPTS.get(role, ROLE_PROMPTS[AgentRole.ENGINEER])
    
    if task_context:
        base_prompt += f"\n\n**Current Task Context:**\n{task_context}"
    
    return base_prompt


class Agent:
    """
    An AI agent with a specific role and model assignment.
    
    Agents can generate responses, use filesystem tools, and parse
    their outputs for file write actions.
    """
    
    # Regex pattern to match file write blocks
    # Matches: ```language path/to/file.ext\ncontent\n```
    # More flexible pattern to catch various formats
    FILE_WRITE_PATTERN = re.compile(
        r'```(\w+)\s+([^\s`]+)\n(.*?)```',
        re.DOTALL | re.IGNORECASE
    )
    
    # Pattern to check for consensus
    CONSENSUS_PATTERN = re.compile(r'\[CONSENSUS_REACHED\]', re.IGNORECASE)
    
    def __init__(
        self,
        role_name: str,
        model_id: str,
        client: OpenRouterClient,
        filesystem: FileSystemTools | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        custom_system_prompt: str | None = None,
        memory_store: AgentMemoryStore | None = None,
        enable_persistent_memory: bool = True,
    ):
        """
        Initialize an agent.

        Args:
            role_name: The agent's role name (e.g., "Planner", "Engineer")
            model_id: The model to use (e.g., "anthropic/claude-3.5-sonnet")
            client: OpenRouter client for API calls
            filesystem: FileSystemTools instance for file operations
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            custom_system_prompt: Optional custom system prompt (overrides role-based prompt)
            memory_store: Optional AgentMemoryStore for persistent memory
            enable_persistent_memory: Whether to load/save memory across sessions
        """
        self.role_name = role_name
        self.model_id = model_id
        self._client = client
        self._filesystem = filesystem or FileSystemTools()
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Use custom prompt if provided, otherwise use role-based prompt
        if custom_system_prompt:
            self.system_prompt = custom_system_prompt
        else:
            # Try to find matching AgentRole enum
            try:
                role = AgentRole[role_name.upper()]
                self.system_prompt = get_system_prompt_for_role(role)
            except (KeyError, ValueError):
                # Use Engineer as default if role not found
                self.system_prompt = get_system_prompt_for_role(AgentRole.ENGINEER)

        # Conversation history for this agent
        self._conversation_history: list[ChatMessage] = []

        # Persistent memory across sessions
        self._memory_store = memory_store or (get_memory_store() if enable_persistent_memory else None)
        self._persistent_memory: AgentSessionMemory | None = None
        self._enable_persistent_memory = enable_persistent_memory and self._memory_store is not None

        # Load persistent memory if enabled
        if self._enable_persistent_memory and self._memory_store:
            self._load_persistent_memory()
    
    @property
    def conversation_history(self) -> list[ChatMessage]:
        """Get the conversation history."""
        return self._conversation_history.copy()
    
    def clear_history(self) -> None:
        """Clear the session conversation history (not persistent memory)."""
        self._conversation_history.clear()

    def _load_persistent_memory(self) -> None:
        """Load this agent's persistent memory from disk."""
        if self._memory_store:
            self._persistent_memory = self._memory_store.load_memory(self.role_name)

            # Prepend key learnings to system prompt for context
            if self._persistent_memory.key_learnings:
                learnings_str = "\n".join(
                    f"- {learning}" for learning in self._persistent_memory.key_learnings[-10:]
                )
                self.system_prompt += (
                    f"\n\n**KEY LEARNINGS FROM PRIOR SESSIONS:**\n"
                    f"You have worked on this project before. Here are important "
                    f"decisions and context from prior sessions:\n{learnings_str}"
                )

    def save_persistent_memory(self) -> bool:
        """Save this agent's persistent memory to disk."""
        if not self._memory_store or not self._persistent_memory:
            return False

        # Update persistent memory with current session data
        for msg in self._conversation_history:
            self._persistent_memory.add_message(
                role=msg.role,
                content=msg.content,
                name=msg.name,
            )

        return self._memory_store.save_memory(self.role_name)

    def get_memory_summary(self) -> dict | None:
        """Get a summary of this agent's persistent memory."""
        if not self._memory_store or not self._persistent_memory:
            return None
        return self._memory_store.get_memory_summary(self.role_name)

    def add_message(self, role: str, content: str, name: str | None = None) -> None:
        """
        Add a message to the conversation history.
        
        Args:
            role: Message role ("user", "assistant", or "system")
            content: Message content
            name: Optional name for the message
        """
        self._conversation_history.append(ChatMessage(
            role=role,
            content=content,
            name=name or self.role_name
        ))
    
    def _parse_file_writes(self, content: str) -> list[FileWriteAction]:
        """
        Parse file write actions from agent output.
        
        Args:
            content: The agent's response content
            
        Returns:
            List of FileWriteAction objects
        """
        file_writes = []
        
        for match in self.FILE_WRITE_PATTERN.finditer(content):
            language, path, file_content = match.groups()
            
            # Clean up the content (remove leading/trailing whitespace)
            file_content = file_content.strip()
            
            file_writes.append(FileWriteAction(
                path=path.strip(),
                content=file_content,
                language=language.strip()
            ))
        
        return file_writes
    
    def _check_consensus(self, content: str) -> bool:
        """Check if the response indicates consensus was reached."""
        return bool(self.CONSENSUS_PATTERN.search(content))
    
    async def _execute_file_writes(
        self, 
        file_writes: list[FileWriteAction]
    ) -> list[tuple[str, bool, str]]:
        """
        Execute file write actions.
        
        Args:
            file_writes: List of FileWriteAction objects
            
        Returns:
            List of tuples (path, success, message)
        """
        results = []
        
        for action in file_writes:
            try:
                written_path = await self._filesystem.write_file(
                    action.path,
                    action.content
                )
                results.append((written_path, True, f"Successfully wrote {written_path}"))
            except Exception as e:
                results.append((action.path, False, f"Failed to write {action.path}: {e}"))
        
        return results
    
    async def generate_response(
        self,
        conversation_history: list[ChatMessage],
        stream: bool = False,
        execute_writes: bool = True,
    ) -> AgentResponse:
        """
        Generate a response using the AI model.
        
        Args:
            conversation_history: List of messages for context
            stream: Whether to stream the response
            execute_writes: Whether to automatically execute file writes
            
        Returns:
            AgentResponse with content and parsed actions
        """
        # Make the API call
        response = await self._client.chat_completion(
            messages=conversation_history,
            model=self.model_id,
            system_prompt=self.system_prompt,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=stream,
        )
        
        # Handle streaming vs non-streaming
        if stream:
            # For streaming, we collect the full response first
            # (file writes need the complete content)
            content_parts = []
            async for chunk in response:
                content_parts.append(chunk)
            content = "".join(content_parts)
            chat_response = None
        else:
            content = response.content
            chat_response = response
        
        # Parse file writes
        file_writes = self._parse_file_writes(content)

        # Execute file writes if requested
        if execute_writes and file_writes:
            await self._execute_file_writes(file_writes)
        
        # Check for consensus
        consensus_reached = self._check_consensus(content)
        
        return AgentResponse(
            content=content,
            role_name=self.role_name,
            model_used=self.model_id,
            file_writes=file_writes,
            consensus_reached=consensus_reached,
            raw_response=chat_response,
        )
    
    async def generate_response_stream(
        self,
        conversation_history: list[ChatMessage],
    ) -> AsyncGenerator[tuple[str, bool, list[FileWriteAction]], None]:
        """
        Generate a streaming response.
        
        Yields:
            Tuples of (chunk, is_complete, file_writes)
            - chunk: The text chunk
            - is_complete: True when response is complete
            - file_writes: List of file writes (only populated at end)
        """
        content_parts = []
        
        async for chunk in await self.generate_response(
            conversation_history,
            stream=True,
            execute_writes=False,
        ):
            content_parts.append(chunk)
            yield (chunk, False, [])
        
        # Final yield with complete content and parsed actions
        full_content = "".join(content_parts)
        file_writes = self._parse_file_writes(full_content)
        self._check_consensus(full_content)
        
        yield ("", True, file_writes)
    
    def __repr__(self) -> str:
        return f"Agent(role={self.role_name}, model={self.model_id})"


def create_agent_for_role(
    role: AgentRole,
    model_id: str,
    client: OpenRouterClient,
    filesystem: FileSystemTools | None = None,
    task_context: str = "",
) -> Agent:
    """
    Factory function to create an agent for a specific role.
    
    Args:
        role: The agent role
        model_id: Model to use
        client: OpenRouter client
        filesystem: FileSystemTools instance
        task_context: Optional task context for the system prompt
        
    Returns:
        Configured Agent instance
    """
    system_prompt = get_system_prompt_for_role(role, task_context)

    agent = Agent(
        role_name=role.value,
        model_id=model_id,
        client=client,
        filesystem=filesystem,
    )
    
    # Override with custom system prompt if task context provided
    if task_context:
        agent.system_prompt = system_prompt
    
    return agent
