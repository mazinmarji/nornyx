# GOAL-050 Risk Note

This patch is planning-only. It does not create split schemas, change schema routing, change CLI behavior, change checker behavior, or remove compatibility support.

Residual risk is future migration breakage if the schema split is implemented without registry tests or compatibility aliases. The plan requires additive schema files first, then registry tests, then documentation updates, with a separate approval before changing default behavior.
