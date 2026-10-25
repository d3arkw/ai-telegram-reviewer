import asyncio
import json
import sys
import tempfile
from pathlib import Path

from google.genai import types


async def run_ruff(code: str) -> str:
    with tempfile.NamedTemporaryFile(
        suffix=".py", mode="w", encoding="utf-8", delete=False
    ) as tmp:
        tmp.write(code)
        path = tmp.name
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--output-format",
            "json",
            path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
        except TimeoutError:
            proc.kill()
            return "RUFF_ERROR: превышен таймаут"
        try:
            diagnostics = json.loads(stdout.decode("utf-8") or "[]")
        except json.JSONDecodeError:
            return "RUFF_ERROR: не получилось разобрать вывод"
        if not diagnostics:
            return "OK: проблем не найдено"
        lines = []
        for d in diagnostics[:10]:
            loc = d.get("location", {})
            lines.append(
                f"{d.get('code', '?')} строка {loc.get('row', 0)}: {d.get('message', '')}"
            )
        return "\n".join(lines)
    finally:
        Path(path).unlink(missing_ok=True)


RUFF_GEMINI_DECLARATION = types.FunctionDeclaration(
    name="run_ruff",
    description="Запускает линтер ruff на проверяемом коде и возвращает найденные проблемы",
    parameters=types.Schema(type="OBJECT", properties={}),
)


RUFF_OPENAI_TOOL = {
    "type": "function",
    "function": {
        "name": "run_ruff",
        "description": "Запускает линтер ruff на проверяемом коде и возвращает найденные проблемы",
        "parameters": {"type": "object", "properties": {}},
    },
}
