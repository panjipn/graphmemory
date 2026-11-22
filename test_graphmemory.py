"""Plain-python tests:  python test_graphmemory.py"""
import os
import tempfile

from graphmemory import Memory
from mcp_server import handle

tmp = tempfile.mkdtemp()
store = os.path.join(tmp, "t.rl")
mem = Memory(store)

mem.link("Ana", "leads", "Apollo", a_kind="person", b_kind="project")
mem.link("Apollo", "uses", "Relate", b_kind="tool")
mem.note("Apollo stores telemetry.", entities=["Apollo"])
assert mem.path("Ana", "Relate") == ["Ana", "Apollo", "Relate"]
assert mem.recall("Apollo")["facts"][0]["text"] == "Apollo stores telemetry."
assert mem.stats()["entities"] == 3

# persistence: close first (one writer per store), then a brand-new
# Memory on the same store sees the same graph
mem.close()
mem2 = Memory(store)
assert mem2.path("Ana", "Relate") == ["Ana", "Apollo", "Relate"]

# MCP surface: initialize + tools/list + tools/call round-trip
r = handle(mem2, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
assert r["result"]["serverInfo"]["name"] == "graphmemory"
r = handle(mem2, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
assert len(r["result"]["tools"]) == 7
r = handle(mem2, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                  "params": {"name": "find_path", "arguments": {"a": "Ana", "b": "Relate"}}})
assert "Ana" in r["result"]["content"][0]["text"]

print("all tests passed")
