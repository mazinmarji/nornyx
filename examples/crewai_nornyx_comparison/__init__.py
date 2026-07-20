"""Framework-native CrewAI x Nornyx 1.7.0 A/B comparison example.

Two controlled variants of one customer-support workflow run the same real
CrewAI ``Agent``/``Task``/``Crew`` objects, deterministic offline model, tools,
and inputs. Variant A is ordinary CrewAI; Variant B adds Nornyx governance on
the integrated path. The example is deterministic and fully offline.

The modules are used as top-level imports after the example directory is placed
on ``sys.path`` (which ``common`` does on import), mirroring the repository's
other agentic-network examples. See ``compare.py`` for the entrypoint.
"""
