"""
Agent Memory Persistence for MultiCode.

Allows agents to reference prior conversation turns across sessions.
Each agent's conversation history is saved and loaded from disk,
enabling continuity between separate MultiCode runs.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from api.openrouter import ChatMessage

logger = logging.getLogger(__name__)

# Storage location
MEMORY_DIR = Path.home() / ".multicode" / "agent_memory"


@dataclass
class AgentMemoryEntry:
    """A single conversation entry for an agent."""
    role: str
    content: str
    name: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_chat_message(self) -> ChatMessage:
        """Convert to ChatMessage for API calls."""
        return ChatMessage(
            role=self.role,
            content=self.content,
            name=self.name,
        )

    @classmethod
    def from_chat_message(cls, message: ChatMessage) -> AgentMemoryEntry:
        """Create from a ChatMessage."""
        return cls(
            role=message.role,
            content=message.content,
            name=message.name,
        )


@dataclass
class AgentSessionMemory:
    """Complete memory for a single agent across all sessions."""
    agent_name: str
    total_sessions: int = 0
    total_turns: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    # Persistent conversation history (accumulates across sessions)
    conversation_history: list[AgentMemoryEntry] = field(default_factory=list)
    # Key decisions/summaries extracted from past sessions
    key_learnings: list[str] = field(default_factory=list)
    # Files this agent has worked on
    files_touched: list[str] = field(default_factory=list)

    def add_message(self, role: str, content: str, name: str | None = None) -> None:
        """Add a message to this agent's persistent history."""
        entry = AgentMemoryEntry(role=role, content=content, name=name)
        self.conversation_history.append(entry)
        self.total_turns += 1
        self.last_updated = datetime.now().isoformat()

    def get_recent_context(self, max_entries: int = 50) -> list[ChatMessage]:
        """Get recent conversation history as ChatMessages for API context."""
        entries = self.conversation_history[-max_entries:]
        return [entry.to_chat_message() for entry in entries]

    def get_full_history(self) -> list[ChatMessage]:
        """Get full conversation history as ChatMessages."""
        return [entry.to_chat_message() for entry in self.conversation_history]

    def add_key_learning(self, learning: str) -> None:
        """Extract and store a key learning/decision from a session."""
        if learning and learning not in self.key_learnings:
            self.key_learnings.append(learning)
            # Keep learnings manageable
            if len(self.key_learnings) > 20:
                self.key_learnings = self.key_learnings[-20:]

    def add_file_touched(self, file_path: str) -> None:
        """Track which files this agent has worked on."""
        if file_path and file_path not in self.files_touched:
            self.files_touched.append(file_path)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentSessionMemory:
        """Deserialize from dictionary."""
        memory = cls(
            agent_name=data.get("agent_name", "Unknown"),
            total_sessions=data.get("total_sessions", 0),
            total_turns=data.get("total_turns", 0),
            created_at=data.get("created_at", datetime.now().isoformat()),
            last_updated=data.get("last_updated", datetime.now().isoformat()),
            conversation_history=[
                AgentMemoryEntry(**entry) if isinstance(entry, dict) else entry
                for entry in data.get("conversation_history", [])
            ],
            key_learnings=data.get("key_learnings", []),
            files_touched=data.get("files_touched", []),
        )
        return memory


class AgentMemoryStore:
    """
    Persistent storage for agent memories across sessions.

    Each agent has a JSON file storing their conversation history,
    key learnings, and files they've worked on.
    """

    def __init__(self, memory_dir: Path | None = None):
        self.memory_dir = memory_dir or MEMORY_DIR
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self._loaded_memories: dict[str, AgentSessionMemory] = {}

    def _get_memory_path(self, agent_name: str) -> Path:
        """Get the file path for an agent's memory."""
        # Sanitize filename
        safe_name = agent_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
        return self.memory_dir / f"{safe_name}.json"

    def load_memory(self, agent_name: str) -> AgentSessionMemory:
        """
        Load an agent's persistent memory from disk.

        Args:
            agent_name: The agent's name/role

        Returns:
            AgentSessionMemory (empty if no prior memory exists)
        """
        if agent_name in self._loaded_memories:
            return self._loaded_memories[agent_name]

        memory_path = self._get_memory_path(agent_name)

        if memory_path.exists():
            try:
                with open(memory_path, encoding='utf-8') as f:
                    data = json.load(f)
                memory = AgentSessionMemory.from_dict(data)
                logger.info(
                    f"Loaded memory for '{agent_name}': "
                    f"{memory.total_sessions} sessions, {memory.total_turns} turns, "
                    f"{len(memory.key_learnings)} key learnings"
                )
                self._loaded_memories[agent_name] = memory
                return memory
            except Exception as e:
                logger.error(f"Failed to load memory for '{agent_name}': {e}")

        # Create new memory
        memory = AgentSessionMemory(agent_name=agent_name)
        self._loaded_memories[agent_name] = memory
        return memory

    def save_memory(self, agent_name: str) -> bool:
        """
        Save an agent's persistent memory to disk.

        Args:
            agent_name: The agent's name/role

        Returns:
            True if saved successfully
        """
        memory = self._loaded_memories.get(agent_name)
        if not memory:
            return False

        memory_path = self._get_memory_path(agent_name)

        try:
            memory.total_sessions += 1
            memory.last_updated = datetime.now().isoformat()

            with open(memory_path, 'w', encoding='utf-8') as f:
                json.dump(memory.to_dict(), f, indent=2, ensure_ascii=False)

            logger.info(
                f"Saved memory for '{agent_name}': "
                f"{memory.total_sessions} sessions, {memory.total_turns} turns"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to save memory for '{agent_name}': {e}")
            return False

    def save_all(self) -> int:
        """Save all loaded agent memories. Returns count of saved memories."""
        count = 0
        for agent_name in list(self._loaded_memories.keys()):
            if self.save_memory(agent_name):
                count += 1
        return count

    def clear_memory(self, agent_name: str) -> bool:
        """Delete an agent's memory file and cached data."""
        memory_path = self._get_memory_path(agent_name)
        self._loaded_memories.pop(agent_name, None)

        if memory_path.exists():
            try:
                memory_path.unlink()
                logger.info(f"Memory cleared for '{agent_name}'")
                return True
            except Exception as e:
                logger.error(f"Failed to clear memory for '{agent_name}': {e}")
        return False

    def get_memory_summary(self, agent_name: str) -> dict[str, Any]:
        """Get a summary of an agent's memory without loading everything."""
        memory = self.load_memory(agent_name)
        return {
            "agent_name": memory.agent_name,
            "total_sessions": memory.total_sessions,
            "total_turns": memory.total_turns,
            "conversation_entries": len(memory.conversation_history),
            "key_learnings": len(memory.key_learnings),
            "files_touched": memory.files_touched,
            "last_updated": memory.last_updated,
        }

    def list_all_memories(self) -> list[dict[str, Any]]:
        """List all agent memories on disk."""
        memories = []
        for memory_file in sorted(self.memory_dir.glob("*.json")):
            try:
                with open(memory_file, encoding='utf-8') as f:
                    data = json.load(f)
                memories.append({
                    "agent_name": data.get("agent_name", memory_file.stem),
                    "total_sessions": data.get("total_sessions", 0),
                    "total_turns": data.get("total_turns", 0),
                    "file": str(memory_file),
                    "last_updated": data.get("last_updated", "unknown"),
                })
            except Exception:
                pass
        return memories


# Global memory store
_memory_store: AgentMemoryStore | None = None


def get_memory_store() -> AgentMemoryStore:
    """Get or create the global agent memory store."""
    global _memory_store
    if _memory_store is None:
        _memory_store = AgentMemoryStore()
    return _memory_store


def reset_memory_store() -> None:
    """Reset the global memory store (for testing/cleanup)."""
    global _memory_store
    _memory_store = None
