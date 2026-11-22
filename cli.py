"""GraphMemory command-line demo.

  python cli.py --store demo.rl ingest examples/notes
  python cli.py --store demo.rl ask "what is connected to Relate?"
  python cli.py --store demo.rl ask "how are Panji and Neo4j connected?"
  python cli.py --store demo.rl stats
  python cli.py --store demo.rl export graph.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys

from graphmemory import Memory


def ask(mem: Memory, question: str) -> str:
    q = question.strip().rstrip("?")
    m = re.match(r"how are (.+) and (.+) connected", q, re.I)
    if m:
        chain = mem.path(m.group(1), m.group(2))
        if not chain:
            return f"No connection found between {m.group(1)} and {m.group(2)} yet."
        return " → ".join(chain)
    m = re.match(r"(?:what is connected to|what do you know about|recall|about)\s+(.+)", q, re.I)
    if m:
        name = m.group(1).strip()
        r = mem.recall(name)
        lines = [f"{name}:"]
        for d in r["direct"]:
            arrow = "→" if d["outgoing"] else "←"
            lines.append(f"  {arrow} {d['relation']}: {d['name']} ({d['kind']})")
        for f in r["facts"]:
            lines.append(f"  • {f['text']}")
        if len(lines) == 1:
            lines.append("  (nothing stored yet)")
        return "\n".join(lines)
    hits = mem.search(q)
    if hits["entities"] or hits["facts"]:
        out = [f"Matches for '{q}':"]
        out += [f"  entity: {e['name']} ({e['kind']})" for e in hits["entities"]]
        out += [f"  fact: {f['text']}" for f in hits["facts"]]
        return "\n".join(out)
    return "I don't have anything about that yet — teach me with remember/link/note."


def main() -> None:
    ap = argparse.ArgumentParser(prog="graphmemory")
    ap.add_argument("--store", default="graphmemory.rl")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_ing = sub.add_parser("ingest"); p_ing.add_argument("folder")
    p_ask = sub.add_parser("ask"); p_ask.add_argument("question")
    sub.add_parser("stats")
    p_exp = sub.add_parser("export"); p_exp.add_argument("outfile")
    args = ap.parse_args()

    mem = Memory(args.store)
    if args.cmd == "ingest":
        print(json.dumps(mem.ingest_markdown(args.folder), indent=2))
    elif args.cmd == "ask":
        print(ask(mem, args.question))
    elif args.cmd == "stats":
        print(json.dumps(mem.stats(), indent=2))
    elif args.cmd == "export":
        data = mem.export()
        with open(args.outfile, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        print(f"exported {len(data['nodes'])} nodes, {len(data['edges'])} edges -> {args.outfile}")


if __name__ == "__main__":
    sys.exit(main())
