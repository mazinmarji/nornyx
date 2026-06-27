# GOAL-063 Risk Note

Risk is medium. This goal makes Nornyx Graph more product-visible, which increases the chance that readers mistake declared graph relationships for executable runtime transitions.

Mitigation: the expanded graph guide and example explicitly state that graph edges are semantic, audit, and control relationships, not executable transitions. Tests also assert the static safety boundary and absence of live connector declarations.

No graph execution, tool execution, model calls, live connectors, package publication, deployment, automatic approval, self-modification, or GOAL-100 promotion was added.
