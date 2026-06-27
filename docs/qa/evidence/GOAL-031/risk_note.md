# GOAL-031 Risk Note

Risk is medium because KPI scores can be over-read as approval or objective
product success.

The implementation keeps KPI scoring local and deterministic. It does not call
LLMs, connectors, external telemetry, GitHub APIs, remote benchmark services,
deployments, or production monitoring. KPI failures can flag weak evidence, but
KPI success does not approve, merge, release, or publish anything.
