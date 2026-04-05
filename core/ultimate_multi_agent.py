"""
Ultimate Dynamic Multi-Agent System for MultiCode.

Features:
- AI creates custom agents and workflows
- Full file operations: CREATE, READ, EDIT (partial/full)
- Voting system for disagreements
- Complete visibility - user sees everything
- Smart conflict resolution
- Real-time progress tracking
- Comprehensive logging
"""

import logging
import re
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from api.openrouter import ChatMessage, OpenRouterClient

logger = logging.getLogger(__name__)


class UltimateMultiAgentSystem:
    """
    Ultimate multi-agent system with full AI control and visibility.

    Every thought, discussion, vote, and action is visible to the user.
    """

    def __init__(
        self,
        client: OpenRouterClient,
        model_id: str,
        filesystem: Any,
        audit_logger: Any = None,
    ):
        self.client = client
        self.model_id = model_id
        self.filesystem = filesystem
        self.audit_logger = audit_logger
        self.agents = {}
        self.workflow = []
        self.files_created = []
        self.files_modified = []
        self.conversation_history = []
        self.voting_history = []

    async def _load_agent_memories(self, agent_names: list[str]) -> dict[str, str]:
        """Load recent context for each agent from persistent memory store."""
        try:
            from core.agent_memory import get_memory_store
            store = get_memory_store()
            memories = {}
            for name in agent_names:
                summary = store.get_memory_summary(name)
                if summary and summary.get("key_learnings"):
                    # Include last 5 key learnings as context
                    memories[name] = "\n".join(summary["key_learnings"][-5:])
            return memories
        except Exception as e:
            logger.debug("Could not load agent memories: %s", e)
            return {}
    
    async def read_directory_context(self) -> str:
        """Read current directory to understand existing files."""
        try:
            cwd = Path.cwd()
            files = []
            for item in cwd.iterdir():
                if not item.name.startswith('.'):
                    files.append(f"  {'📁 ' if item.is_dir() else '📄 '}{item.name}")
            
            if files:
                return "Current directory contents:\n" + "\n".join(files)
            else:
                return "Current directory is empty."
        except Exception as e:
            logger.error(f"Failed to read directory: {e}")
            return "Could not read directory."
    
    async def stream_ultimate_session(
        self,
        user_input: str,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Run the ultimate multi-agent session with full visibility.
        """
        # Step 1: Read directory
        yield {
            'type': 'info',
            'content': '📂 Reading directory to understand existing files...',
        }
        
        dir_context = await self.read_directory_context()
        yield {
            'type': 'directory',
            'content': dir_context,
        }
        
        # Step 2: AI creates custom team
        yield {
            'type': 'info',
            'content': '🤖 AI analyzing task and creating custom team...',
        }
        
        team_setup = await self._create_dynamic_team(user_input, dir_context)
        
        # Store team and workflow
        self.agents = {agent['name']: agent for agent in team_setup.get('agents', [])}
        self.workflow = team_setup.get('workflow', [])
        
        # Show team and workflow to user
        yield {
            'type': 'team_revealed',
            'agents': team_setup.get('agents', []),
            'workflow': team_setup.get('workflow', []),
        }
        
        # Step 3: Execute workflow
        for step_idx, step in enumerate(self.workflow, 1):
            yield {
                'type': 'workflow_step',
                'step_number': step_idx,
                'total_steps': len(self.workflow),
                'step': step,
            }
            
            assigned_agents = step.get('agents', [])
            
            if not assigned_agents:
                yield {
                    'type': 'info',
                    'content': f'⏭️  Step {step_idx} skipped (no agents assigned)',
                }
                continue
            
            # Execute step with assigned agents
            async for event in self._execute_workflow_step(
                step_idx,
                step,
                assigned_agents,
                user_input,
            ):
                yield event
        
        # Step 4: Final review with voting
        yield {
            'type': 'info',
            'content': f'🗳️  Final review and voting (all {len(self.agents)} agents)...',
        }
        
        async for event in self._final_review_and_voting(user_input):
            yield event
        
        # Summary
        summary_lines = [f'Task complete!']
        if self.files_created:
            summary_lines.append(f'Files created: {len(self.files_created)}')
            for f in self.files_created:
                summary_lines.append(f'  • {f}')
        if self.files_modified:
            summary_lines.append(f'Files modified: {len(self.files_modified)}')
            for f in self.files_modified:
                summary_lines.append(f'  • {f}')

        # Save agent memories
        agent_names = list(self.agents.keys()) if self.agents else []
        memories = await self._load_agent_memories(agent_names)
        for agent_name in agent_names:
            try:
                from core.agent_memory import get_memory_store
                store = get_memory_store()
                store.save_memory(agent_name)
            except Exception as e:
                logger.debug("Failed to save memory for %s: %s", agent_name, e)

        # Log session completion to audit trail
        if self.audit_logger:
            from core.audit import AuditAction
            for agent_name in agent_names:
                if agent_name in memories:
                    self.audit_logger.log(
                        AuditAction.MEMORY_SAVED,
                        agent=agent_name,
                        detail={"key_learnings_count": len(memories[agent_name].splitlines())},
                    )
            self.audit_logger.log(
                AuditAction.SESSION_END,
                detail={
                    "files_created": self.files_created,
                    "files_modified": self.files_modified,
                    "agents_used": agent_names,
                },
                files_affected=self.files_created + self.files_modified,
            )

        yield {
            'type': 'done',
            'content': '\n'.join(summary_lines),
        }
    
    async def _create_dynamic_team(
        self,
        user_input: str,
        dir_context: str,
    ) -> dict[str, Any]:
        """AI creates custom agents and workflow."""
        
        prompt = f"""You are designing a custom multi-agent team for this task.

User request: {user_input}

{dir_context}

Your task:
1. Create 2-5 CUSTOM agent roles needed for THIS specific task
2. Define each agent's name, role, and expertise
3. Create a detailed workflow with clear steps
4. Assign 1+ agents to each workflow step

**Output Format (STRICT):**

AGENTS
AgentName: Role description and expertise
AnotherAgent: Another role description

WORKFLOW
1. Task description | AgentName, AnotherAgent
2. Another task | AgentName
3. Final task | AgentName, Reviewer

**Example:**
AGENTS
HTMLArchitect: Creates semantic HTML structures with accessibility
CSSDesigner: Designs beautiful responsive UI with modern CSS
JavaScriptDev: Implements interactive functionality and APIs
QualityAssurance: Tests functionality and validates requirements

WORKFLOW
1. Create HTML structure | HTMLArchitect
2. Add CSS styling | CSSDesigner, HTMLArchitect
3. Implement JavaScript | JavaScriptDev
4. Test and validate | QualityAssurance, JavaScriptDev

Now create team for: {user_input}

Respond in the exact format above."""
        
        try:
            response = await self.client.chat_completion(
                messages=[ChatMessage(role="user", content=prompt)],
                model=self.model_id,
                temperature=0.3,
                max_tokens=2500,
            )

            # Log API call with token usage
            if self.audit_logger:
                from core.audit import AuditAction
                tokens = response.usage.get("total_tokens", 0) if response.usage else 0
                cost = 0.0  # Would need model pricing data to calculate
                self.audit_logger.log(
                    AuditAction.API_CALL,
                    detail={"action": "create_team", "model": self.model_id, "tokens": tokens},
                    tokens_used=tokens,
                    cost_estimate_usd=cost,
                )

            return self._parse_team_setup(response.content)
        except Exception as e:
            logger.error(f"Failed to create team: {e}")
            return {
                'agents': [
                    {'name': 'Developer', 'role': 'Creates the solution'},
                    {'name': 'Reviewer', 'role': 'Reviews and validates'},
                ],
                'workflow': [
                    {'task': 'Create solution', 'agents': ['Developer']},
                    {'task': 'Review work', 'agents': ['Reviewer']},
                ],
            }
    
    def _parse_team_setup(self, content: str) -> dict[str, Any]:
        """Parse AI response to extract agents and workflow."""
        agents = []
        workflow = []
        
        # Parse AGENTS section
        agents_match = re.search(r'AGENTS\s*\n(.*?)(?:WORKFLOW|$)', content, re.DOTALL | re.IGNORECASE)
        if agents_match:
            agents_text = agents_match.group(1)
            for line in agents_text.strip().split('\n'):
                if ':' in line:
                    parts = line.split(':', 1)
                    agents.append({
                        'name': parts[0].strip(),
                        'role': parts[1].strip(),
                    })
        
        # Parse WORKFLOW section
        workflow_match = re.search(r'WORKFLOW\s*\n(.*?)$', content, re.DOTALL | re.IGNORECASE)
        if workflow_match:
            workflow_text = workflow_match.group(1)
            for line in workflow_text.strip().split('\n'):
                if '|' in line:
                    parts = line.split('|')
                    task = parts[0].strip()
                    if '.' in task:
                        task = task.split('.', 1)[1].strip()
                    agent_names = [a.strip() for a in parts[1].split(',')]
                    workflow.append({
                        'task': task,
                        'agents': agent_names,
                    })
        
        return {
            'agents': agents if agents else [],
            'workflow': workflow if workflow else [],
        }
    
    async def _execute_workflow_step(
        self,
        step_idx: int,
        step: dict[str, Any],
        assigned_agents: list[str],
        user_input: str,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Execute a single workflow step with assigned agents."""
        
        if len(assigned_agents) > 1:
            # Multiple agents - discussion mode
            yield {
                'type': 'info',
                'content': f'💬 {len(assigned_agents)} agents collaborating...',
            }
            
            discussion_context = [
                ChatMessage(role="system", content="Team discussion with full project awareness."),
                ChatMessage(role="user", content=f"User request: {user_input}"),
                ChatMessage(role="assistant", content=f"Full workflow:\n" + "\n".join([
                    f"  {i}. {s.get('task', 'Task')} → {', '.join(s.get('agents', []))}"
                    for i, s in enumerate(self.workflow, 1)
                ])),
                ChatMessage(role="assistant", content=f"Current step ({step_idx}/{len(self.workflow)}): {step.get('task')}"),
                ChatMessage(role="assistant", content=f"Assigned to: {', '.join(assigned_agents)}"),
            ]
            
            for agent_name in assigned_agents:
                if agent_name not in self.agents:
                    continue
                
                agent = self.agents[agent_name]
                
                discussion_history = "\n".join([
                    f"{msg.role}: {msg.content}" 
                    for msg in discussion_context[-10:]
                ])
                
                yield {
                    'type': 'agent_thinking',
                    'agent': agent_name,
                    'role': agent.get('role', 'Specialist'),
                }
                
                agent_output = await self._agent_discuss(
                    agent_name,
                    agent,
                    user_input,
                    step,
                    discussion_history,
                    step_idx,
                    len(self.workflow),
                )
                
                yield {
                    'type': 'agent_speaking',
                    'agent': agent_name,
                    'role': agent.get('role', 'Specialist'),
                    'content': agent_output,
                }
                
                discussion_context.append(
                    ChatMessage(role="assistant", content=f"{agent_name}: {agent_output}")
                )
                
                # Process file operations from agent output
                async for file_event in self._process_file_operations(agent_output):
                    yield file_event
        else:
            # Single agent
            agent_name = assigned_agents[0]
            
            if agent_name not in self.agents:
                yield {
                    'type': 'error',
                    'content': f'⚠️  Assigned agent {agent_name} not found',
                }
                return
            
            agent = self.agents[agent_name]
            
            yield {
                'type': 'agent_thinking',
                'agent': agent_name,
                'role': agent.get('role', 'Specialist'),
            }
            
            agent_output = await self._agent_execute(
                agent_name,
                agent,
                user_input,
                step,
                step_idx,
                len(self.workflow),
            )
            
            yield {
                'type': 'agent_speaking',
                'agent': agent_name,
                'role': agent.get('role', 'Specialist'),
                'content': agent_output,
            }
            
            # Process file operations
            async for file_event in self._process_file_operations(agent_output):
                yield file_event
    
    async def _agent_discuss(
        self,
        agent_name: str,
        agent: dict[str, Any],
        user_input: str,
        step: dict[str, Any],
        discussion_history: str,
        step_idx: int,
        total_steps: int,
    ) -> str:
        """Agent participates in team discussion."""
        
        prompt = f"""You are {agent_name}.

Your role: {agent.get('role', 'Specialist')}

User request: {user_input}

**Full Project Workflow:**
{discussion_history}

**Current Step:** {step_idx}/{total_steps} - {step.get('task', 'Complete the task')}

**Your Task:**
1. Read the full discussion above
2. Respond to other agents' points naturally
3. Share your expertise on this step
4. If you need to CREATE files: [CREATE filename.ext]...[/CREATE]
5. If you need to EDIT files: [EDIT filename.ext start_line:end_line]...[/EDIT]
6. If you need to READ files: [READ filename.ext]

**File Operation Tags:**
- [CREATE filename.ext] full content [/CREATE]
- [EDIT filename.ext 10:20] new lines 10-20 [/EDIT]
- [READ filename.ext]

**Discuss naturally and collaborate!**"""
        
        try:
            response = await self.client.chat_completion(
                messages=[ChatMessage(role="user", content=prompt)],
                model=self.model_id,
                temperature=0.6,
                max_tokens=3000,
            )

            # Track tokens in audit
            if self.audit_logger and response.usage:
                from core.audit import AuditAction
                tokens = response.usage.get("total_tokens", 0)
                self.audit_logger.log(
                    AuditAction.API_CALL,
                    agent=agent_name,
                    detail={"action": "agent_discuss", "model": self.model_id, "tokens": tokens},
                    tokens_used=tokens,
                )

            return response.content
        except Exception as e:
            logger.error(f"Agent {agent_name} error: {e}")
            return f"[{agent_name} encountered an error: {e}]"
    
    async def _agent_execute(
        self,
        agent_name: str,
        agent: dict[str, Any],
        user_input: str,
        step: dict[str, Any],
        step_idx: int,
        total_steps: int,
    ) -> str:
        """Single agent executes step alone."""
        
        prompt = f"""You are {agent_name}.

Your role: {agent.get('role', 'Specialist')}

User request: {user_input}

**Current Step:** {step_idx}/{total_steps} - {step.get('task', 'Complete the task')}

**Your Task:**
1. Complete this step with your expertise
2. If you need to CREATE files: [CREATE filename.ext]...[/CREATE]
3. If you need to EDIT files: [EDIT filename.ext start_line:end_line]...[/EDIT]
4. If you need to READ files: [READ filename.ext]

**File Operation Tags:**
- [CREATE filename.ext] full content [/CREATE]
- [EDIT filename.ext 10:20] new lines 10-20 [/EDIT]
- [READ filename.ext]

**Work efficiently and create high-quality results!**"""
        
        try:
            response = await self.client.chat_completion(
                messages=[ChatMessage(role="user", content=prompt)],
                model=self.model_id,
                temperature=0.5,
                max_tokens=3000,
            )

            # Track tokens in audit
            if self.audit_logger and response.usage:
                from core.audit import AuditAction
                tokens = response.usage.get("total_tokens", 0)
                self.audit_logger.log(
                    AuditAction.API_CALL,
                    agent=agent_name,
                    detail={"action": "agent_execute", "model": self.model_id, "tokens": tokens},
                    tokens_used=tokens,
                )

            return response.content
        except Exception as e:
            logger.error(f"Agent {agent_name} error: {e}")
            return f"[{agent_name} encountered an error: {e}]"
    
    async def _process_file_operations(
        self,
        agent_output: str,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Process CREATE, EDIT, READ operations from agent output."""
        
        # Process CREATE operations
        create_pattern = r'\[CREATE\s+([^\]]+)\]\n(.*?)\[/CREATE\]'
        for match in re.finditer(create_pattern, agent_output, re.DOTALL | re.IGNORECASE):
            filename = match.group(1).strip()
            content = match.group(2).strip()
            
            yield {
                'type': 'creating_file',
                'file': filename,
            }
            
            try:
                written_path = await self.filesystem.write_file(filename, content)
                self.files_created.append(written_path)

                from datetime import datetime
                timestamp = datetime.now().strftime("%H:%M:%S")
                file_logger = logging.getLogger('multicode.files')
                file_logger.info(f"[{timestamp}] INFO CREATE File '{written_path}' [✓]")

                # Audit event
                if self.audit_logger:
                    from core.audit import AuditAction
                    self.audit_logger.log(
                        AuditAction.FILE_CREATED,
                        detail={"path": written_path, "size": len(content)},
                        files_affected=[written_path],
                    )
                
                yield {
                    'type': 'file_created',
                    'file': written_path,
                }
            except Exception as e:
                yield {
                    'type': 'file_error',
                    'file': filename,
                    'error': str(e),
                }
        
        # Process EDIT operations
        edit_pattern = r'\[EDIT\s+([^\]]+)\s+(\d+):(\d+)\]\n(.*?)\[/EDIT\]'
        for match in re.finditer(edit_pattern, agent_output, re.DOTALL | re.IGNORECASE):
            filename = match.group(1).strip()
            start_line = int(match.group(2))
            end_line = int(match.group(3))
            new_content = match.group(4).strip()
            
            yield {
                'type': 'editing_file',
                'file': filename,
                'lines': f'{start_line}-{end_line}',
            }
            
            try:
                # Read current file
                current_content = await self.filesystem.read_file(filename)
                current_lines = current_content.split('\n')
                
                # Replace lines
                new_lines = new_content.split('\n')
                current_lines[start_line-1:end_line] = new_lines
                
                # Write back
                updated_content = '\n'.join(current_lines)
                written_path = await self.filesystem.write_file(filename, updated_content)
                
                if written_path not in self.files_modified:
                    self.files_modified.append(written_path)
                
                from datetime import datetime
                timestamp = datetime.now().strftime("%H:%M:%S")
                file_logger = logging.getLogger('multicode.files')
                file_logger.info(f"[{timestamp}] INFO EDIT File '{written_path}' lines {start_line}-{end_line} [✓]")
                
                yield {
                    'type': 'file_edited',
                    'file': written_path,
                    'lines': f'{start_line}-{end_line}',
                }
            except Exception as e:
                yield {
                    'type': 'file_error',
                    'file': filename,
                    'error': str(e),
                }
        
        # Process READ operations
        read_pattern = r'\[READ\s+([^\]]+)\]'
        for match in re.finditer(read_pattern, agent_output, re.IGNORECASE):
            filename = match.group(1).strip()
            
            yield {
                'type': 'reading_file',
                'file': filename,
            }
            
            try:
                content = await self.filesystem.read_file(filename)
                
                from datetime import datetime
                timestamp = datetime.now().strftime("%H:%M:%S")
                file_logger = logging.getLogger('multicode.files')
                file_logger.info(f"[{timestamp}] INFO READ File '{filename}' [✓]")
                
                yield {
                    'type': 'file_read',
                    'file': filename,
                    'content': content[:500] + ('...' if len(content) > 500 else ''),
                }
            except Exception as e:
                yield {
                    'type': 'file_error',
                    'file': filename,
                    'error': str(e),
                }
    
    async def _final_review_and_voting(
        self,
        user_input: str,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Final review with voting system."""
        
        # Each agent reviews and votes
        votes = {}
        
        for agent_name, agent in self.agents.items():
            yield {
                'type': 'agent_thinking',
                'agent': agent_name,
                'role': agent.get('role', 'Specialist'),
            }
            
            review = await self._agent_review(agent_name, agent, user_input)
            
            yield {
                'type': 'agent_speaking',
                'agent': agent_name,
                'role': agent.get('role', 'Specialist'),
                'content': review,
            }
            
            # Extract vote
            vote_match = re.search(r'\[VOTE:\s*(APPROVE|REJECT|MODIFY)\]', review, re.IGNORECASE)
            if vote_match:
                vote = vote_match.group(1).upper()
                votes[agent_name] = vote
        
        # Count votes
        approve_count = sum(1 for v in votes.values() if v == 'APPROVE')
        reject_count = sum(1 for v in votes.values() if v == 'REJECT')
        modify_count = sum(1 for v in votes.values() if v == 'MODIFY')
        
        yield {
            'type': 'voting_results',
            'votes': votes,
            'approve': approve_count,
            'reject': reject_count,
            'modify': modify_count,
        }
        
        # Determine outcome
        total = len(votes)
        if approve_count > total / 2:
            yield {
                'type': 'info',
                'content': f'✅ Project APPROVED ({approve_count}/{total} votes)',
            }
        elif modify_count > total / 2:
            yield {
                'type': 'info',
                'content': f'🔧 Modifications needed ({modify_count}/{total} votes)',
            }
        else:
            yield {
                'type': 'info',
                'content': f'❌ Project needs revision ({reject_count}/{total} reject votes)',
            }
    
    async def _agent_review(
        self,
        agent_name: str,
        agent: dict[str, Any],
        user_input: str,
    ) -> str:
        """Agent provides final review and vote."""
        
        files_created = ', '.join(self.files_created) if self.files_created else 'none'
        
        prompt = f"""You are {agent_name}.

Your role: {agent.get('role', 'Specialist')}

User request: {user_input}

**Files Created:** {files_created}

**Final Review:**
Review the completed work and provide your assessment.

End your review with a vote:
- [VOTE: APPROVE] - Work is complete and meets requirements
- [VOTE: REJECT] - Work has major issues, needs significant revision
- [VOTE: MODIFY] - Work is good but needs minor modifications

Provide your honest review and vote."""
        
        try:
            response = await self.client.chat_completion(
                messages=[ChatMessage(role="user", content=prompt)],
                model=self.model_id,
                temperature=0.4,
                max_tokens=2000,
            )

            # Track tokens in audit
            if self.audit_logger and response.usage:
                from core.audit import AuditAction
                tokens = response.usage.get("total_tokens", 0)
                self.audit_logger.log(
                    AuditAction.API_CALL,
                    agent=agent_name,
                    detail={"action": "agent_review", "model": self.model_id, "tokens": tokens},
                    tokens_used=tokens,
                )

            return response.content
        except Exception as e:
            logger.error(f"Agent {agent_name} review error: {e}")
            return f"[{agent_name} review error: {e}] [VOTE: MODIFY]"
