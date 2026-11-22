# GraphMemory — persistent graph memory for AI agents

AI agents forget everything when the session ends. **GraphMemory gives an
agent a memory that survives**: facts, entities and the relationships
between them, stored as a property graph in
[Relate](https://relatedb.ai) — Neo4j's embedded, open-source graph
database — in a single local store. No server, no account, no network.

An agent teaches the memory in one session (`remember`, `link`, `note`)
and recalls it in the next — including *multi-hop* recall: "How are Panji
and Neo4j connected?" is answered by traversing the graph
(`Panji → GraphMemory → Relate → Neo4j`), not by keyword search.

Built for the **Relate by Neo4j Hackathon 2026** (topic: `relate`).

## Why a graph?

Agent memory is not a bag of documents — it is *connected context*:
people work on projects, projects use tools, tools are made by
organizations. A graph database stores those connections natively, so
recall can follow them: direct neighbours, everything reachable within
N hops, and the shortest path between any two things the agent knows.

## Quick start

```bash
pip install -r requirements.txt        # installs relate-db

python demo.py                         # two sessions, one memory
python test_graphmemory.py             # library + MCP round-trip tests
```

The demo runs session 1 (teach), exits the process, then runs session 2
as a **separate process** — which recalls everything anyway, because the
graph lives in the Relate store `demo.rl` on disk.

## Use it from an MCP host

GraphMemory ships an MCP server (stdio, JSON-RPC) with seven tools:
`remember_entity`, `link_entities`, `add_note`, `recall`, `find_path`,
`search_memory`, `memory_stats`.

```bash
python mcp_server.py my-memory.rl
```

Point any MCP-compatible host at that command and the host's agent gains
a persistent memory shared across sessions.

## CLI

```bash
python cli.py --store demo.rl ingest examples/notes
python cli.py --store demo.rl ask "what is connected to Relate?"
python cli.py --store demo.rl ask "how are Panji and Neo4j connected?"
python cli.py --store demo.rl stats
python cli.py --store demo.rl export graph.json   # then open visualize.html
```

`ingest` turns a folder of Markdown notes into connected context:
`[[wiki links]]` and `` `backticked` `` terms become entities, documents
become nodes, and entities mentioned together become related.

## How it uses Relate

- **Embedded Python API** (`import relate`, package `relate-db` 1.2.0):
  the engine runs in-process — zero deployment.
- **Cypher** for everything: `MERGE` upserts, variable-length traversal
  (`[:RELATES*1..2]`) for recall, `shortestPath` for connection queries.
- **Persistent single-file/directory store** (`.rl`) with one writer —
  the memory is a file you can copy, back up, and version.
- The MCP server is a thin JSON-RPC layer over the same library, so the
  CLI, the tests, and any MCP host all share one memory implementation.

## Layout

| File | What it is |
|---|---|
| `graphmemory.py` | The memory library (schema, ingest, queries) |
| `mcp_server.py` | MCP server exposing the memory as agent tools |
| `cli.py` | Command-line demo (`ingest`, `ask`, `stats`, `export`) |
| `demo.py` | Two-session persistence demo |
| `visualize.html` | Single-file graph visualizer for an exported JSON |
| `examples/notes/` | Sample Markdown knowledge base |
| `test_graphmemory.py` | Tests: library, persistence, MCP round-trip |

## AI use disclosure

This project was built with substantial help from an AI coding assistant
(Muse), as the hackathon rules allow: the assistant wrote code from a
human-written design, and every feature was verified by running the
tests and demos above. The idea, design decisions, and submission are
the author's.

## License

Apache-2.0 (see `LICENSE`). Relate itself is Apache-2.0 by Neo4j.
