"""GraphMemory — persistent graph memory for AI agents, powered by Relate.

Relate (Neo4j's embedded graph database) stores everything in a single
local store: no server, no account, no network. The memory survives process
restarts, so an agent can learn in one session and recall in the next.

Graph model
-----------
(:Entity {name, kind})            people, projects, tools, concepts, places
(:Fact   {text, source, ts})      a note the agent learned
(:Doc    {title, path})           an ingested document

(:Entity)-[:RELATES {relation}]->(:Entity)
(:Fact)-[:ABOUT]->(:Entity)
(:Doc)-[:MENTIONS]->(:Entity)
(:Entity)-[:APPEARS_IN]->(:Doc)
"""

from __future__ import annotations

import re
import time
from pathlib import Path

import relate


def _norm(name: str) -> str:
    return " ".join(name.strip().split())


class Memory:
    def __init__(self, path: str = "graphmemory.rl"):
        self.db = relate.connect(path)
        self.store_path = path

    def close(self) -> None:
        """Release the store. Relate allows one writer per store, so close
        before another process (or Memory) opens the same file."""
        self.db.close()

    # ------------------------------------------------------------------ #
    # writing
    # ------------------------------------------------------------------ #
    def remember(self, name: str, kind: str = "concept") -> dict:
        name = _norm(name)
        rows = self._q(
            "MERGE (e:Entity {name: $name}) "
            "ON CREATE SET e.kind = $kind, e.created = $ts "
            "RETURN e.name AS name, e.kind AS kind",
            {"name": name, "kind": kind, "ts": time.time()},
        )
        return rows[0]

    def link(self, a: str, relation: str, b: str,
             a_kind: str = "concept", b_kind: str = "concept") -> dict:
        self.remember(a, a_kind)
        self.remember(b, b_kind)
        rel = re.sub(r"[^A-Za-z0-9_]", "_", relation.strip().lower()) or "relates"
        self._q(
            "MATCH (x:Entity {name: $a}), (y:Entity {name: $b}) "
            f"MERGE (x)-[r:RELATES {{relation: $rel}}]->(y) "
            "RETURN type(r) AS t",
            {"a": _norm(a), "b": _norm(b), "rel": rel},
        )
        return {"from": _norm(a), "relation": rel, "to": _norm(b)}

    def note(self, text: str, entities: list[str] | None = None,
             source: str = "agent") -> dict:
        rows = self._q(
            "CREATE (f:Fact {text: $text, source: $source, ts: $ts}) "
            "RETURN id(f) AS id",
            {"text": text.strip(), "source": source, "ts": time.time()},
        )
        fid = rows[0]["id"]
        for name in entities or []:
            self.remember(name)
            self._q(
                "MATCH (f:Fact), (e:Entity {name: $name}) "
                "WHERE id(f) = $fid MERGE (f)-[:ABOUT]->(e) RETURN f",
                {"fid": fid, "name": _norm(name)},
            )
        return {"id": fid, "text": text.strip(), "entities": entities or []}

    # ------------------------------------------------------------------ #
    # reading
    # ------------------------------------------------------------------ #
    def recall(self, name: str, depth: int = 2) -> dict:
        """Everything connected to an entity, up to `depth` hops away."""
        name = _norm(name)
        direct = self._q(
            "MATCH (e:Entity {name: $name})-[r:RELATES]-(other:Entity) "
            "RETURN other.name AS name, other.kind AS kind, r.relation AS relation, "
            "startNode(r) = e AS outgoing",
            {"name": name},
        )
        wide = self._q(
            f"MATCH (e:Entity {{name: $name}})-[:RELATES*1..{int(depth)}]-(other:Entity) "
            "RETURN DISTINCT other.name AS name, other.kind AS kind",
            {"name": name},
        )
        facts = self._q(
            "MATCH (f:Fact)-[:ABOUT]->(e:Entity {name: $name}) "
            "RETURN f.text AS text, f.source AS source ORDER BY f.ts",
            {"name": name},
        )
        return {"entity": name, "direct": direct, "reachable": wide, "facts": facts}

    def path(self, a: str, b: str) -> list[str] | None:
        """Shortest chain of entities connecting a and b (multi-hop reasoning)."""
        rows = self._q(
            "MATCH p = shortestPath((x:Entity {name: $a})-[:RELATES*..8]-(y:Entity {name: $b})) "
            "RETURN [n IN nodes(p) | n.name] AS chain",
            {"a": _norm(a), "b": _norm(b)},
        )
        return rows[0]["chain"] if rows else None

    def search(self, text: str) -> dict:
        q = text.strip().lower()
        entities = self._q(
            "MATCH (e:Entity) WHERE toLower(e.name) CONTAINS $q "
            "RETURN e.name AS name, e.kind AS kind",
            {"q": q},
        )
        facts = self._q(
            "MATCH (f:Fact) WHERE toLower(f.text) CONTAINS $q "
            "RETURN f.text AS text, f.source AS source",
            {"q": q},
        )
        return {"entities": entities, "facts": facts}

    def stats(self) -> dict:
        def count(q):
            return self._q(q)[0]["n"]
        return {
            "entities": count("MATCH (e:Entity) RETURN count(e) AS n"),
            "relationships": count("MATCH ()-[r:RELATES]->() RETURN count(r) AS n"),
            "facts": count("MATCH (f:Fact) RETURN count(f) AS n"),
            "documents": count("MATCH (d:Doc) RETURN count(d) AS n"),
        }

    def export(self) -> dict:
        nodes = self._q("MATCH (e:Entity) RETURN e.name AS name, e.kind AS kind")
        edges = self._q(
            "MATCH (a:Entity)-[r:RELATES]->(b:Entity) "
            "RETURN a.name AS from, b.name AS to, r.relation AS relation"
        )
        return {"nodes": nodes, "edges": edges}

    # ------------------------------------------------------------------ #
    # ingestion: a folder of Markdown notes becomes connected context
    # ------------------------------------------------------------------ #
    def ingest_markdown(self, folder: str) -> dict:
        folder = Path(folder)
        docs = sorted(folder.glob("*.md"))
        entities_seen: set[str] = set()
        for doc in docs:
            text = doc.read_text(encoding="utf-8")
            title = next(
                (ln.lstrip("# ").strip() for ln in text.splitlines() if ln.startswith("#")),
                doc.stem,
            )
            self._q(
                "MERGE (d:Doc {title: $title}) SET d.path = $path RETURN d",
                {"title": title, "path": str(doc)},
            )
            # [[wiki links]] and `backticked terms` are explicit entities;
            # a shared entity across documents is what connects the graph.
            found = set(re.findall(r"\[\[([^\]]+)\]\]", text))
            found |= set(re.findall(r"`([^`]{2,40})`", text))
            for name in sorted(found):
                name = _norm(name)
                if not name:
                    continue
                entities_seen.add(name)
                self.remember(name)
                self._q(
                    "MATCH (d:Doc {title: $title}), (e:Entity {name: $name}) "
                    "MERGE (d)-[:MENTIONS]->(e) MERGE (e)-[:APPEARS_IN]->(d) RETURN d",
                    {"title": title, "name": name},
                )
            # entities mentioned in the same document are related context
            fl = sorted(found)
            for i, a in enumerate(fl):
                for b in fl[i + 1:]:
                    self.link(a, "mentioned_with", b)
            self.note(f"Document '{title}' mentions: {', '.join(fl)}",
                      entities=fl, source=f"ingest:{doc.name}")
        return {"documents": len(docs), "entities": len(entities_seen)}

    # ------------------------------------------------------------------ #
    def _q(self, cypher: str, params: dict | None = None) -> list[dict]:
        cur = self.db.execute(cypher, params or {})
        out = []
        for row in cur:
            try:
                out.append(row.to_dict())
            except Exception:
                out.append(dict(row))
        return out
