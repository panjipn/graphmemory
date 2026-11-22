"""GraphMemory MCP server — gives any MCP host a persistent graph memory.

Speaks the Model Context Protocol over stdio (JSON-RPC 2.0). The memory
itself lives in a Relate store on disk, so it persists across sessions and
across hosts: learn something in one agent session, recall it in another.

Run:  python mcp_server.py [path-to-store.rl]
"""

from __future__ import annotations

import json
import sys

from graphmemory import Memory

TOOLS = [
    {
        "name": "remember_entity",
        "description": "Remember an entity (person, project, tool, concept, place) in the graph memory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "kind": {"type": "string", "default": "concept"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "link_entities",
        "description": "Record a relationship between two entities, e.g. link_entities('Ana', 'works_on', 'Apollo').",
        "inputSchema": {
            "type": "object",
            "properties": {
                "a": {"type": "string"},
                "relation": {"type": "string"},
                "b": {"type": "string"},
            },
            "required": ["a", "relation", "b"],
        },
    },
    {
        "name": "add_note",
        "description": "Store a fact/note and attach it to the entities it is about.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "entities": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["text"],
        },
    },
    {
        "name": "recall",
        "description": "Recall everything connected to an entity: direct relations, reachable entities within 2 hops, and facts about it.",
        "inputSchema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
    {
        "name": "find_path",
        "description": "Find the shortest chain of relationships connecting two entities (multi-hop reasoning).",
        "inputSchema": {
            "type": "object",
            "properties": {"a": {"type": "string"}, "b": {"type": "string"}},
            "required": ["a", "b"],
        },
    },
    {
        "name": "search_memory",
        "description": "Search entities and facts whose text contains a keyword.",
        "inputSchema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {
        "name": "memory_stats",
        "description": "Counts of entities, relationships, facts and documents in the memory.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def call_tool(mem: Memory, name: str, args: dict):
    if name == "remember_entity":
        return mem.remember(args["name"], args.get("kind", "concept"))
    if name == "link_entities":
        return mem.link(args["a"], args["relation"], args["b"])
    if name == "add_note":
        return mem.note(args["text"], args.get("entities", []), source="mcp")
    if name == "recall":
        return mem.recall(args["name"])
    if name == "find_path":
        return {"chain": mem.path(args["a"], args["b"])}
    if name == "search_memory":
        return mem.search(args["text"])
    if name == "memory_stats":
        return mem.stats()
    raise ValueError(f"unknown tool: {name}")


def handle(mem: Memory, msg: dict) -> dict | None:
    method = msg.get("method", "")
    mid = msg.get("id")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "graphmemory", "version": "1.0.0"},
        }}
    if method == "notifications/initialized":
        return None
    if method == "ping":
        return {"jsonrpc": "2.0", "id": mid, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = msg.get("params", {})
        try:
            result = call_tool(mem, params.get("name", ""), params.get("arguments", {}))
            text = json.dumps(result, indent=2, default=str)
            return {"jsonrpc": "2.0", "id": mid, "result": {
                "content": [{"type": "text", "text": text}], "isError": False}}
        except Exception as exc:  # surface the error to the host, keep serving
            return {"jsonrpc": "2.0", "id": mid, "result": {
                "content": [{"type": "text", "text": f"error: {exc}"}], "isError": True}}
    if mid is not None:
        return {"jsonrpc": "2.0", "id": mid,
                "error": {"code": -32601, "message": f"method not found: {method}"}}
    return None


def main() -> None:
    store = sys.argv[1] if len(sys.argv) > 1 else "graphmemory.rl"
    mem = Memory(store)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        reply = handle(mem, msg)
        if reply is not None:
            sys.stdout.write(json.dumps(reply) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
