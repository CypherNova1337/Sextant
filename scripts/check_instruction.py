"""Run a submission against a scripted model with the scorer's compaction settings.

The submission is compiled with the competition's own loader and run by ADK's
Runner, with the session state the harness creates (`problem_description`)
and the scorer's EventsCompactionConfig. The scripted model reads large files
until the reported prompt size passes the compaction threshold several times,
then submits. For every model request the script prints whether the problem
statement is in the system instruction and whether the original task message
is still among the request contents.

Usage: python scripts/check_instruction.py AGENT_DIR [TASK_INDEX] [--expect-task]
With --expect-task, exits non-zero unless every agent request carries the
problem statement in its system instruction.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import AsyncGenerator

from adk_submission import ModelRegistry, compile_submission
from google.adk.apps.app import App, EventsCompactionConfig
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from swegemma.config import build_submission_limits

ROOT = Path(__file__).resolve().parent.parent
MODEL = "gemma-4-31b-it-qat-w4a16-ct"
TASK_MESSAGE = "You are evaluating a software engineering task"
FILLER = "value = compute(value)  # a line of code to make the file long\n" * 180
READS = 14
LOG: list[dict] = []  # module level: the loader works on a copy of the model object


class ScriptedLlm(BaseLlm):
    """Reads files, then submits; answers summary requests with a fixed text.

    Reports prompt size as characters / 4, the estimate ADK itself uses.
    """

    model: str = "scripted"
    step: int = 0

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        system = (llm_request.config.system_instruction if llm_request.config else None) or ""
        system = system if isinstance(system, str) else str(system)
        parts = [p for c in llm_request.contents for p in (c.parts or [])]
        chars = len(system) + sum(
            len(p.text or "")
            + (len(json.dumps(p.function_response.response)) if p.function_response else 0)
            + (len(json.dumps(p.function_call.args)) if p.function_call else 0)
            for p in parts
        )
        texts = " ".join(p.text or "" for p in parts)
        summary = len(llm_request.contents) == 1 and texts.startswith("The following is a conversation history")
        LOG.append({"summary": summary, "system": system, "contents": len(llm_request.contents),
                         "tokens": chars // 4, "task_message": TASK_MESSAGE in texts})
        usage = types.GenerateContentResponseUsageMetadata(
            prompt_token_count=chars // 4, candidates_token_count=50, total_token_count=chars // 4 + 50)
        if summary:
            text = "Summary: the agent read several files and is about to edit."
            yield LlmResponse(content=types.Content(role="model", parts=[types.Part(text=text)]), usage_metadata=usage)
            return
        self.step += 1
        if self.step <= READS:
            call = types.FunctionCall(name="read_file", args={"filepath": f"pkg/module{self.step}.py"})
        elif self.step == READS + 1:
            call = types.FunctionCall(name="submit_patch", args={})
        else:
            yield LlmResponse(content=types.Content(role="model", parts=[types.Part(text="Done.")]), usage_metadata=usage)
            return
        parts = [types.Part(text=f"Call {self.step}", thought=True), types.Part(function_call=call)]
        yield LlmResponse(content=types.Content(role="model", parts=parts), usage_metadata=usage)


def run_command(command: str) -> str: return "{}"
def read_file(filepath: str, start_line: int | None = None, end_line: int | None = None) -> str: return FILLER
def write_file(filepath: str, content: str) -> str: return "{}"
def edit_file(filepath: str, old_string: str, new_string: str, allow_multiple: bool = False) -> str: return "{}"
def submit_patch() -> str: return json.dumps({"status": "ok", "patch_size": 10, "files_changed": 1})
def get_status() -> str: return "{}"
def get_code_neighbors(node: str, edge_type: str | None = None, max_neighbors: int = 50) -> str: return "{}"
def search_similar_code(query: str, k: int = 10) -> str: return "{}"
def get_code_subgraph(nodes: list[str]) -> str: return "{}"


TOOLS = {f.__name__: f for f in (run_command, read_file, write_file, edit_file, submit_patch, get_status,
                                 get_code_neighbors, search_similar_code, get_code_subgraph)}


async def run(agent_dir: Path, task: dict) -> list[dict]:
    limits, constraints = build_submission_limits()
    llm = ScriptedLlm()
    models = ModelRegistry()
    models.register(MODEL, llm)
    agent = compile_submission(agent_dir, TOOLS, models, limits=limits, generation_constraints=constraints)
    sessions = InMemorySessionService()
    session = await sessions.create_session(
        app_name="swegemma_eval", user_id="eval_user", state={"problem_description": task["problem_statement"]})
    app = App(name="swegemma_eval", root_agent=agent, events_compaction_config=EventsCompactionConfig(
        compaction_interval=5, overlap_size=2, token_threshold=14336, event_retention_size=5))
    message = types.Content(role="user", parts=[types.Part(
        text=f"{TASK_MESSAGE} for repository {task['repo']}.\n\nProblem Statement:\n{task['problem_statement']}\n")])
    async for _ in Runner(app=app, session_service=sessions).run_async(
            user_id="eval_user", session_id=session.id, new_message=message):
        pass
    return LOG


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    agent_dir = Path(args[0])
    index = int(args[1]) if len(args) > 1 else 0
    task = json.loads((ROOT / "data" / "tasks.jsonl").read_text().splitlines()[index])
    log = asyncio.run(run(agent_dir, task))
    statement = task["problem_statement"].strip()[:200]
    missing = 0
    for i, r in enumerate(log):
        in_system = statement in r["system"]
        if not r["summary"] and not in_system:
            missing += 1
        print(f"{i:2d} {'summary' if r['summary'] else 'agent  '} contents={r['contents']:2d} "
              f"tokens~{r['tokens']:6d} task_in_instruction={in_system} task_message_in_contents={r['task_message']}")
    compactions = sum(r["summary"] for r in log)
    print(f"{task['instance_id']}: {compactions} compactions, {missing} agent requests without the task in the instruction")
    if "--expect-task" in sys.argv and (missing or not compactions):
        sys.exit(1)


if __name__ == "__main__":
    main()
