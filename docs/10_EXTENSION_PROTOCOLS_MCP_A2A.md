# Extension Protocols: MCP and A2A

Nornyx should integrate with external protocols rather than replace them.

## MCP-style connectors

MCP-style connectors expose tools/data to agents. Nornyx should model them as governed connectors with capability manifests.

```yaml
connectors:
  - name: GitHub
    protocol: MCP
    capabilities:
      - read_repo
      - create_pr
    deny:
      - delete_repo
    security:
      requires_approval: true
      default_mode: read_only
```

## A2A-style peer agents

A2A-style protocols allow agents built on different platforms to coordinate.

```yaml
connectors:
  - name: ExternalSecurityAgent
    protocol: A2A
    capabilities:
      - share_evidence_digest
    share: [vulnerability_summary, evidence_digest]
    never_share: [secrets, credentials, tokens, private_memory]
    security:
      requires_approval: true
      default_mode: contract_only
```

## Extension design

Nornyx should support:

- versioned extensions;
- capability manifests;
- connector policies;
- tool schemas;
- sandbox rules;
- signed packages;
- experimental feature gates.

## Local connector adapter scaffold

GOAL-010 adds a local connector report:

```bash
python -m nornyx.cli connector-plan examples/governed_delivery_control_plane.nyx --out generated/connector_report.json
```

The report:

- recognizes MCP and A2A connector manifests;
- supports plugin-scoped connectors under `experimental.plugins`;
- records declared capabilities, denied actions, share/never-share boundaries,
  approval requirements, and default modes;
- blocks unsupported protocols, missing capabilities, unsafe default modes, live
  endpoint/command targets, undeclared harness connector references, and A2A
  sensitive sharing;
- warns when candidate/stable plugins lack conformance or A2A never-share lists
  are incomplete;
- writes adapter decisions without executing adapters, opening networks,
  loading credentials, running commands, or granting approval.

`schemas/connector_manifest.schema.json` captures the manifest shape used by
this scaffold. The schema and runtime are contract material only; they do not
enable live connector execution.

## v0.4 adapter contract bridge

GOAL-036 adds contract-only adapter metadata for Governed Delivery Control Plane, Agentic
Dev OS, GovernanceAdapter, telecom ops, and business ops. These adapters reference MCP
and A2A connector manifests but keep `execution_mode: contract_only` and
`live_connector_execution: false`.

Adapter contracts must bind to policy, eval, and evidence references before
they are considered conformant. They do not create live connector sessions,
open networks, load credentials, run commands, grant approvals, or deploy.

## v0.7 connector-contract conformance

GOAL-039 adds static adapter conformance reports and a connector-contract
conformance schema. The report checks adapter connector refs, policy refs, eval
refs, evidence refs, connector protocol declarations, default modes, approval
requirements, and shared safety non-goals.

The report embeds the existing connector manifest report and keeps all safety
flags disabled: no connectors enabled, no adapters executed, no network used,
no commands executed, and no credentials loaded.
