from dataclasses import dataclass


@dataclass
class StreamingDelta:
    role: str | None = None
    content: str | None = None
    function_call: dict | None = None
    tool_calls: list | None = None
    name: str | None = None
