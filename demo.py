"""Two-session demo: the whole point of GraphMemory.

Session 1 teaches the memory some facts and exits.
Session 2 is a *new process* — it recalls them anyway, because the graph
lives in a Relate store on disk. Run:  python demo.py [store-path]
"""

import sys

from graphmemory import Memory

STORE = sys.argv[1] if len(sys.argv) > 1 else "demo.rl"


def session1() -> None:
    mem = Memory(STORE)
    print("— Session 1: teaching the agent —")
    mem.link("Ana", "leads", "Project Apollo", a_kind="person", b_kind="project")
    mem.link("Project Apollo", "stores_data_in", "Relate", b_kind="tool")
    mem.link("Relate", "made_by", "Neo4j", b_kind="organization")
    mem.link("Panji", "builds", "GraphMemory", a_kind="person", b_kind="project")
    mem.link("GraphMemory", "built_on", "Relate", b_kind="tool")
    mem.note("Frenzy Finish doubles points in the last 10 seconds of a round.",
             entities=["GraphMemory"], source="session-1")
    print("stats:", mem.stats())
    mem.close()
    print("(session 1 process exits — memory must survive on disk)")


def session2() -> None:
    mem = Memory(STORE)
    print("\n— Session 2: a new process recalls —")
    print("What is connected to Relate?")
    for d in mem.recall("Relate")["direct"]:
        print("  ", d["relation"], "→", d["name"])
    print("\nHow are Panji and Neo4j connected?")
    print("  ", " → ".join(mem.path("Panji", "Neo4j") or []))
    print("\nFacts about GraphMemory:")
    for f in mem.recall("GraphMemory")["facts"]:
        print("  •", f["text"])
    print("stats:", mem.stats())


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[2] == "session2":
        session2()
    else:
        # session 2 runs as a separate process: persistence is proven for
        # real, not by reopening a handle in the same interpreter.
        import subprocess
        session1()
        subprocess.run([sys.executable, __file__, STORE, "session2"], check=True)
