---
chapter: 27
part: V
title: "Tool Protocols and Package Governance"
---

# Tool Protocols and Package Governance

> **Opening scenario.** A researcher in Northstar's Research & Insights division finds exactly what the Atlas assistant is missing: an open-source tool bundle that would let Atlas pull structured filings data instead of scraping summaries. The bundle's README is reassuring — "documentation and configuration only, no network calls, runs entirely locally" — and the researcher files a request to add it to Atlas's toolset. The platform engineer who picks up the ticket does not read the README first. She unpacks the bundle into a scratch directory and looks at the files, and finds three things the README did not mention: a `package.json` with a `postinstall` script, a hidden directory containing a tool-server configuration that mounts the filesystem root, and a config file with a line that looks like an API token. None of these has done anything, because nothing has been installed or executed. The question the ticket now poses is not "is this bundle malicious?" — nobody can answer that from a scan — but a more tractable one: *what must be true, and recorded, and approved, before code written by strangers is allowed to become part of an agent's reachable capability set?* This chapter is about that question, and about its quieter twin: how to declare a tool-protocol integration in a governance contract without the declaration itself becoming a live wire.

> **Learning objectives.**
> - Describe the Model Context Protocol and agent-to-agent protocols neutrally, and explain why each creates a governance surface rather than a governance solution.
> - Separate the two distinct concerns this chapter governs: third-party tool packages as supply-chain input, and protocol integrations as declared boundaries.
> - Run a deterministic package scan, name its detector categories, and read its reports — including the claim-versus-evidence mismatches that make untrusted self-description computable.
> - State the code-asserted non-claims of the package scanner, and explain why "inventoried, risk-surfaced, evidence-bound, hash-locked, and approval-gated" is the strongest honest sentence a scan can support.
> - Explain how a contract-only protocol declaration describes an integration boundary while making endpoints, credentials, and commands structurally unrepresentable.
> - Distinguish an implemented declaration surface from a guidance-level publication pattern and from roadmap-status extension descriptors, and label each correctly.

> **Prerequisites.** Chapter 6 for trust zones and never-share categories; Chapter 10 for decision and enforcement separation; Chapter 13 for assurance tiers; Chapter 14 for coverage and negative controls; Chapter 16 for the status badges; Chapter 18 for locks and digests; Chapter 26 for what external enforcement would add to everything here.

## 27.1 Two protocols, two governance concerns

The <span class="ix" data-ix="Model Context Protocol">Model Context Protocol</span> (MCP) is an open protocol that standardizes how applications provide context and tools to language models: a client — typically the application hosting the model — connects to one or more MCP servers, each of which exposes resources, prompts, and tools through a common interface [@mcp-spec]. Its value is the value of any successful interface standard. A tool written once as an MCP server works with any conforming client, so an ecosystem of reusable servers has grown quickly — filesystem access, database queries, ticketing systems, web retrieval — and connecting an agent to a new capability has dropped from an integration project to a configuration entry. Nothing in that sentence is a criticism. It is, however, a precise description of a new supply chain: the configuration entry names a server, the server is code, and the code was written by someone outside the organization's review process.

<span class="ix" data-ix="Agent2Agent protocol">Agent-to-agent protocols</span> address the peer case rather than the tool case. The Agent2Agent (A2A) protocol lets agents built on different frameworks and operated by different parties discover one another's advertised capabilities and coordinate work across organizational boundaries [@a2a-spec]. From a governance standpoint the difference from MCP is the direction of trust: an MCP server is a capability the agent *uses*, while an A2A peer is a counterparty the agent *works with* — one that has its own goals, its own instructions, and its own view of the interaction. Everything Chapter 6 said about ingress content and authority confusion applies to a peer agent's messages with full force. This book treats A2A declarations alongside MCP declarations because the repository treats them identically at the schema level, and the chapter notes the differences where they matter.

Two governance concerns follow from these protocols, and they are distinct enough that mixing them produces confused architecture. The first is **the package problem**: a tool bundle — an MCP server, its configuration, its install scripts, its documentation — arrives from outside and asks to be adopted. This is supply-chain risk in the classic sense that supply-chain risk-management practice addresses [@nist-scrm], sharpened by the fact that the consumer is an agent: a package that would merely be dependency risk in a conventional application becomes, once wired to a model, a set of reachable actions whose invocation is decided by a planner reading untrusted text. Threat catalogues for agentic systems rank tool-supply-chain compromise and tool misuse among the primary risks precisely because the tool boundary is where text becomes action [@owasp-agentic]. The second is **the declaration problem**: the organization's own governance contract must be able to *say* "this agent integrates with this protocol target, under these constraints" — and the saying must not smuggle in execution. A declaration that contains an endpoint and a credential is not a description of an integration; it is the integration, waiting for an interpreter.

The two concerns get two different mechanisms, and both are implemented at this book's snapshot. Packages are treated as untrusted inert input to a deterministic scanner and an approval-gated adoption profile (Sections 27.2 and 27.3). Protocol integrations are expressed as contract-only declarations whose schemas make live material unrepresentable (Section 27.4). A third pattern — publishing approved documentation *to* model clients through a read-only service — is guidance, not code, and Section 27.5 keeps it firmly on that side of the line.

## 27.2 Tool packages as untrusted inert input

The governing idea is stated in the repository's own documentation before any mechanism: package contents and package claims are untrusted input, and README text, manifest text, and declared capabilities are classified as `untrusted_claim` — never as truth (`docs/governed-package-profile.md`). The mechanism built on that idea is the <span class="ix" data-ix="governed package">governed-package</span> profile **[implemented]**, whose scanner is the rare governance component that is easier to trust because of what it refuses to do: it is local-only, uses no network, follows no symlinks, and never executes, installs, or mutates anything it scans — and it prints `"package_payload_executed": false` in every scan summary as a code-asserted fact rather than a documentation promise (`nornyx/package_scanner.py`, `nornyx/cli.py`).

Three commands cover three adoption postures. `nornyx package scan <src> --out <dir>` runs the deterministic scanner over any directory and writes ten JSON reports with ten Markdown companions. `nornyx package radar <src>` is discovery-first: it reuses the scanner to propose candidate governable units, and every radar report carries `proposal_only: true` — it suggests, and nothing downstream treats a suggestion as a decision **[implemented]**. `nornyx package register <src> --contract <c.nyx>` is adoption: it inventories and scans an existing directory, then hash-locks it, writing a `package_lock.json` that binds source-file hashes, generated-report hashes, and the manifest hash, so that the thing approved is a fixed set of bytes rather than a directory name **[implemented]** (`nornyx/governed_package.py`). Figure 27.1 places the three in the adoption flow.

<figure class="nx-fig" id="fig-27-1">
  <div class="fig-body">
    <div class="flow">
      <div class="node">Third-party bundle<br/>(untrusted inert input)</div>
      <div class="arr">→</div>
      <div class="node">nornyx package scan<br/>deterministic detectors<br/>no execution</div>
      <div class="arr">→</div>
      <div class="node">reports + evidence records<br/>risk tier, claim-vs-evidence</div>
      <div class="arr">→</div>
      <div class="node">register: hash-lock<br/>package_lock.json</div>
      <div class="arr">→</div>
      <div class="node">human approval gate<br/>(AI approvers refused)</div>
      <div class="arr">→</div>
      <div class="node">adoption decision<br/>outside Nornyx</div>
    </div>
  </div>
  <figcaption><b>Figure 27.1 — The package-governance flow.</b> Every solid box up to the approval gate is implemented behavior; the final box is deliberately outside the tool, because installation and execution are downstream responsibilities the profile refuses to perform. The teaching purpose is the position of the approval gate: it sits after evidence exists and after the content is hash-locked, so the human is approving a specific, risk-surfaced, fixed set of bytes — not a package name and a README's self-description.</figcaption>
</figure>

The scanner's detectors are worth enumerating because they define what "risk-surfaced" means, and each maps to a way tool bundles have actually gone wrong (`nornyx/package_scanner.py`):

- **File inventory and digests.** Every file gets a SHA-256, size, extension, and type classification, plus flags for hidden files, binary-like content, oversized files, and long-line or minified text — the shapes in which payloads hide from human review.
- **Secret-like patterns, with hardcoded redaction.** Patterns for cloud access keys, repository and API tokens, private-key headers, bearer tokens, and generic `secret=`-style assignments, alongside credential-named files such as `.env` and `id_rsa`. Every match is rewritten to the literal `REDACTED_SECRET_LIKE_VALUE` before it reaches any report, findings hardcode `raw_value_stored: false`, and the top-level report asserts `raw_secret_values_stored: false` — the scanner cannot be talked into copying a secret into its own evidence **[implemented]**.
- **Hook detection.** Hook directories and lifecycle hook names (`.git/hooks`, `pre-commit`, `preinstall`, `postinstall`, and relatives) plus hook-content keywords — the mechanism by which "just files" becomes "code that runs when you touch it."
- **Protocol-server definitions, with broad-filesystem escalation.** MCP server configuration keys (`mcpServers` and variants) and server-launch command patterns, with severity escalated to critical when the definition grants broad filesystem access (`/`, `~`, `$HOME`, `/etc`, drive roots) or filesystem, browser, network, or database reach.
- **Endpoint classification.** URLs, domains, IP addresses, and localhost ports, classified by function: webhook callback, execution (a download piped to a shell), upload or write target, plain download, or informational.
- **Dangerous-command patterns.** Twenty-three patterns with fixed severities, including `rm -rf`, `curl | sh`, encoded shell invocations, `eval`/`exec` and subprocess calls, base64-decode-and-execute pipes, privileged container flags, cluster and infrastructure apply/destroy commands, and reads of `~/.ssh`, `~/.aws`, and `.env`.
- **Lifecycle scripts.** Shell-script extensions, setup/install/bootstrap-named files, and `package.json` lifecycle entries (`preinstall`, `install`, `postinstall`, `prepare`, and relatives) — the scripts a package manager runs implicitly on install.
- **Claim-versus-evidence mismatches.** The scanner parses README and manifest text for six claim types — docs-only, no-network, no-execution, no-secrets, template-only, local-only — labels every claim source `untrusted_claim`, and cross-checks each claim against its own observations. A package that claims docs-only while risk surfaces are observed, or no-execution while lifecycle scripts exist, produces a critical or high mismatch finding.

Every finding is normalized into an <span class="ix" data-ix="evidence record!package">evidence record</span> with a stable identifier, a severity, a content hash, and honesty fields — `raw_secret_stored`, `network_used`, `execution_used`, `deterministic` — and the <span class="ix" data-ix="risk tier!package scan">risk tier</span> is computed transparently: the tier is the maximum observed severity, the score is the sum of severity ranks, and the report carries an `explanations` list naming which findings produced the number **[implemented]**. There is no model, no weighting oracle, and no judgment call inside the scanner; judgment is the approver's job, and the scanner's job is to make sure the approver is judging evidence rather than marketing.

What the scanner will not say matters as much as what it detects. The profile's documentation lists the <span class="ix" data-ix="non-claim!package safety">non-claims</span>, and the decisive one is last: it does not execute packages, does not install them, does not approve work, does not start MCP servers, does not activate hooks — and "does not claim that a package is safe." The permitted claim is scoped in one sentence that the generated analysis report itself prints: a package was *inventoried, risk-surfaced, evidence-bound, hash-locked, and approval-gated* (`docs/governed-package-profile.md`; `nornyx/package_scanner.py:983`). This is not modesty for its own sake. A scan is a static examination of bytes by pattern; it cannot see obfuscated behavior it has no pattern for, cannot evaluate what code does when run, and cannot certify intent. A tool that reported "safe" would be manufacturing exactly the kind of unfounded claim this book has spent twenty-six chapters teaching readers to reject — and the validation layer backs the posture structurally: gates without evidence, an execution surface or AI tool named as an approver, `installed: true`, `executable_by_default: true`, or any permissive safety flag are validation *failures*, with diagnostics such as `INVALID_APPROVER_EXECUTION_SURFACE` ("execution surfaces and AI tools cannot be eligible approvers") and `UNSAFE_INSTALLATION_POLICY_INSTALLED` observed directly against the repository's negative fixtures **[implemented]**.

## 27.3 A worked scan, and evidence from outside

The repository ships hostile fixtures for exactly this demonstration. The fixture `examples/governed_package/package_with_mcp_config` is two files: a README and a hidden `.claude/mcp.json` declaring a filesystem MCP server mounted at `/`. Listing 27.1 shows the scan, run in a temporary directory against the pinned snapshot.

```bash
$ nornyx package scan examples/governed_package/package_with_mcp_config \
    --out /tmp/nyx-ch27/mcp-scan
{
  "status": "pass",
  "out": "/tmp/nyx-ch27/mcp-scan",
  "package_id": "package",
  "risk_tier": "critical",
  "total_files_scanned": 2,
  "package_payload_executed": false
}
```

**Listing 27.1 — Scanning a hostile fixture.** Real output of `nornyx package scan` on `examples/governed_package/package_with_mcp_config` at the book's snapshot. Two details deserve attention. `"status": "pass"` with `"risk_tier": "critical"` is not a contradiction: the *scan* succeeded, and its finding is critical — the scanner reports, it does not gate. And `"package_payload_executed": false` appears in the summary of every scan, a standing assertion that the risk tier was computed without running anything the package brought with it.

The output directory contains the reports, and reading them is the skill this section teaches. The risk-surface report explains its own number; the MCP review shows the finding with its sanitized excerpt; and the analysis report ends with the permitted claim, verbatim. Listing 27.2 reproduces the load-bearing lines.

```markdown
# Risk Surface Report
- Risk tier: `critical`
- Risk score: `4`
## Explanations
- MCP configs detected: 1 finding(s)
- critical broad filesystem or MCP access observed

# MCP Risk Review
## Critical
- `mcp_server_definition` in `.claude/mcp.json`: {   "mcpServers": {
  "filesystem": { "command": "npx",
  "args": ["@modelcontextprotocol/server-filesystem", "/"] } } }

# Package Analysis
Nornyx treats package contents and claims as untrusted input.
- Statement: This package was inventoried, risk-surfaced, evidence-bound,
  hash-locked, and approval-gated.
```

**Listing 27.2 — Reading the reports.** Excerpts from `risk_surface_report.md`, `mcp_risk_review.md`, and `package_analysis.md` as generated by the scan in Listing 27.1 (MCP excerpt re-wrapped for the page). The finding's JSON evidence record adds the machinery a human summary omits: `severity: critical` with reasons `broad_filesystem_path` and `filesystem_access`, `requires_human_review: true`, a recommendation ("Require MCP risk review before starting any server."), and `execution_used: false`. The closing statement is the strongest sentence the tool permits itself, and it is printed by code, not chosen by a writer.

Run the same command against `examples/governed_package/claim_mismatch_package` — a README claiming "Docs only. No network. No execution. No secrets. Local only." over a `package.json` with a `postinstall` script and a remote homepage — and the claim-versus-evidence report returns four mismatches: `docs_only_but_risk_surfaces_observed` and `no_execution_but_scripts_observed` at critical, `no_network_but_endpoints_observed` and `local_only_but_remote_endpoints_observed` at high, for a critical tier with a risk score of 22. The point of the fixture is pedagogical: the package's *self-description* is the attack surface, and the mismatch detector turns "the README lied" from a discovery made during an incident into a line item produced during intake. Secret handling behaves the same way in the other direction — scanning the radar fixture's `sample-secret-like-config.txt`, whose single line is a token assignment, yields a high-severity `secret_like_pattern` finding whose evidence field contains only `REDACTED_SECRET_LIKE_VALUE`.

External scanners complement the built-in detectors, and the import boundary is deliberately narrow. Exactly two producers can be imported — Syft-style software bills of materials and Gitleaks-style secret-scan reports — and the import is exactly that: Nornyx parses a report file the external tool already wrote; it never executes the external tool, even when the tool's binary is present on the machine **[implemented]** (`nornyx/package_scanner.py`; `nornyx/cli.py`). Listing 27.3 shows both sides of the boundary.

```bash
$ nornyx package evidence import gitleaks report.json --out /tmp/nyx-ch27/ev
{
  "status": "pass",
  "out": "/tmp/nyx-ch27/ev/gitleaks_normalized_evidence.json",
  "evidence_count": 1
}
# the normalized record: source: "external_adapter", status: "imported",
# execution_used: true, network_used: false,
# sanitized_evidence: "REDACTED_SECRET_LIKE_VALUE", raw_secret_stored: false

$ nornyx package evidence import trivy report.json --out /tmp/nyx-ch27/ev
nornyx package evidence import: error: argument tool: invalid choice:
  'trivy' (choose from 'syft', 'gitleaks')
```

**Listing 27.3 — Import-only, from exactly two producers.** Real transcripts at the book's snapshot. The Gitleaks import succeeds and the normalized record is labelled honestly: `status: imported` and `execution_used: true` record that an external scanner ran — *outside* Nornyx — while the secret value itself is redacted on the way in. The Trivy attempt is refused at the command line, whose `choices` list admits only the two supported producers; the handler behind it carries a second guard that rejects any other tool name with the diagnostic `UNSUPPORTED_EVIDENCE_TOOL` (`nornyx/cli.py:305`). An unsupported producer is an error, not a warning — the evidence vocabulary is closed for the same reason the event schema of Chapter 20 is closed.

Adapter declarations in a contract extend this without weakening it: a `.nyx` can declare `evidence_adapters` with a `report_path`, a `required` flag, and a `failure_policy`, and a required adapter whose report is unavailable fails the run — but even then the adapter execution record states, in code, "external tools are not executed automatically; provide report_path to import evidence," and every such record hardcodes `package_payload_executed: false` **[implemented]**. Imports also carry a limit the documentation states plainly: an imported report proves that a report file with these contents existed; it does not prove the external scan was run correctly, recently, or against these exact bytes. Binding imported evidence to the hash-locked package contents is the reviewer's cross-check, which is why the register lock records both source hashes and report hashes side by side.

> **Case study — Atlas.** The filings bundle from the opening scenario goes through intake. The platform engineer runs `nornyx package scan` over the unpacked bundle in a scratch directory: risk tier critical, with three explanation lines — an MCP server definition with a broad filesystem mount, a `postinstall` lifecycle script, and one secret-like pattern, redacted in the report. The claim-versus-evidence report adds `docs_only_but_risk_surfaces_observed`, since the README claimed documentation-only. None of this rejects the bundle; it prices it. The engineer's recommendation to the research lead is *constrain, then adopt*: the filesystem mount is narrowed from `/` to a single read-only data directory before registration; the `postinstall` script is disabled in favour of an explicit, reviewed install step; the secret-like line turns out to be a placeholder, and is removed anyway. The revised bundle is re-scanned, registered with `nornyx package register` so its contents are hash-locked, and put before the research lead as a named human approver — the gate's `denied_approver_types` list means neither Atlas nor any execution surface could have approved it. What Northstar's claim register records is exactly the permitted sentence: the bundle was inventoried, risk-surfaced, evidence-bound, hash-locked, and approval-gated at revision such-and-such — and the residual-risk column records what no scan can supply: the code's runtime behavior is unexamined, and containment at run time is the business of Chapter 26's enforcement points, not of this scan.

## 27.4 Contract-only protocol declarations

The second concern is the organization's own contract describing a protocol integration. The design problem is subtle: the declaration must carry enough to govern — who may use the boundary, in which zones, sharing what, gated how — while carrying nothing that could *operate*. The repository's solution is a closed schema with structural constants **[implemented]**, and it is worth seeing exactly how the door is shut.

A protocol target in an `agentic_network` block declares a `protocol` drawn from a two-value enumeration — `mcp` or `a2a`, nothing else — together with the identities and memberships permitted to use the boundary, the capabilities in play, source and target trust zones, a share list, a non-empty `never_share` list, and required gates, approvals, and evidence (`schemas/agentic_network_v1.schema.json`). Two fields are constants rather than choices: `execution_mode` must be the literal `contract_only`, and `live_connector_execution` must be the literal `false`. And the schema sets `additionalProperties: false`, so the field an integrator would need for a live connection — an endpoint, a port, a credential reference — has nowhere to live. Listing 27.4 shows what happens when someone tries.

```bash
$ nornyx check support_network.nyx --as-of 2026-07-17T00:00:00Z
# after adding `endpoint: https://partner.example.com/a2a` to the target:
{
  "level": "error",
  "code": "GOVERNANCE_BLOCK_SCHEMA_INVALID",
  "message": "Additional properties are not allowed ('endpoint' was unexpected)",
  "path": "agentic_network.protocol_targets.0"
}
# after setting `live_connector_execution: true` instead:
{
  "level": "error",
  "code": "GOVERNANCE_BLOCK_SCHEMA_INVALID",
  "message": "False was expected",
  "path": "agentic_network.protocol_targets.0.live_connector_execution"
}
```

**Listing 27.4 — Live material is unrepresentable.** Real output from two deliberately broken copies of `examples/agentic_network_support/support_network.nyx` at the book's snapshot, each failing `nornyx check` with exit code 1. The first rejection is the closed schema refusing an undeclared field; the second is a schema constant refusing the one value that would change the declaration's nature. "False was expected" is an unusually literal error message, and an unusually honest summary of the design.

Generation adds a second, independent layer. When `nornyx agentic-network generate` renders the declarations into artifacts — including `mcp_capability_declaration.json` and `a2a_declaration.json` — a <span class="ix" data-ix="forbidden-key scanning">forbidden-key scan</span> walks every key and value of the output before it is written. Key segments including `endpoint`, `host`, `port`, `url`, `uri`, `token`, `secret`, `credential`, `password`, `command`, `shell`, and `session`, and key pairs such as `api`+`key` and `private`+`key`, fail generation with `AN_ARTIFACT_FORBIDDEN_FIELD`; string values containing URI schemes or bare IPv4 literals fail with `AN_ARTIFACT_FORBIDDEN_VALUE` (`nornyx/agentic_artifacts.py:78–116, 265–296`) **[implemented]**. The generated MCP declaration for the support network states its own category in a field: `"compatibility": "mcp-compatible declaration; not a runtime, server, endpoint, or transport"`, alongside the constant pair and the denied sensitive categories `credentials`, `private_memory`, `secrets`, and `tokens`. The declaration is also what the network lock binds: each protocol target's identity, protocol, version label, and `contract_only` execution mode appear in the lock's `protocol_declarations` list, so the declared boundary is part of what reviewers approved and what drift detection defends (Chapter 18).

<figure class="nx-fig" id="fig-27-2">
  <div class="fig-body">
    <div class="zones">
      <div class="zone" data-name="zone.support_internal (governed)">
        <div class="node">identity.refund_agent</div>
        <div class="node">capability:<br/>produce_customer_safe_response</div>
      </div>
      <div class="zone" data-name="declared boundary — protocol target (a2a, contract_only)">
        <div class="node">share: customer_response,<br/>evidence_digest</div>
        <div class="node">never_share: secrets, credentials,<br/>tokens, private_memory</div>
        <div class="node">gate + human approval<br/>+ evidence required</div>
      </div>
      <div class="zone untrusted" data-name="zone.customer_channel (external_contract_only)">
        <div class="node">counterparty<br/>(peer agent / client)</div>
      </div>
    </div>
  </div>
  <figcaption><b>Figure 27.2 — The protocol boundary as declared.</b> Drawn from the support example's real protocol target: the middle band is everything the declaration contains — identities, capabilities, share and never-share categories, and required gates, approvals, and evidence — and it contains no transport. The teaching purpose is that the declaration describes an integration boundary without becoming executable configuration: everything needed to review, gate, and audit the crossing is present; everything needed to perform it is absent, and unrepresentable by schema.</figcaption>
</figure>

What does an organization get for a declaration that cannot run? Three things, all of which Chapter 26 depends on. Reviewability: the boundary is a diff in one reviewed file, with human approval requirements attached to the crossing itself. Bindability: the declaration is digest-locked, so an external enforcement point can be configured against a reviewed revision rather than against tribal knowledge. And a computable gap: because the contract names the integration boundary and the runtime configuration lives elsewhere, "does the deployed connector configuration match the declared boundary?" becomes a question with a checkable answer — the comparison itself being work for the reader's pipeline, not the repository's. The prohibition on live connector execution is not a missing feature awaiting maturity; it is repeated in the project's declared non-goals — not "a live MCP/A2A connector runtime" — and enforced in three places: the schema constants, the generation-time scan, and the conformance reports of the older extension surface, which must keep `connectors_enabled: false` and `adapters_executed: false` (`docs/05_SECURITY_MODEL.md`).

> **Misconception.** *"The scanner and the schema together secure our tool supply chain."* They do neither of the two things that sentence implies. The scanner examines bytes at intake; it says nothing about what the code does when a downstream system eventually runs it, and a package can be hostile in ways no pattern list detects. The schema constrains *declarations*; it does not prevent an engineer from wiring a live MCP server into the agent's runtime configuration without ever mentioning it in a contract — that path is exactly the undeclared-surface bypass of Chapter 14, and only inventory discipline and Chapter 26's enforcement points address it. What the pair actually delivers is narrower and still valuable: adoption cannot *quietly* skip evidence and approval, and declaration cannot *quietly* become execution. Quietly is the operative word; loud violations remain possible and remain the enforcement layer's problem.

## 27.5 Publication without authority

There is a third pattern in this chapter, and it must be labelled with more care than the first two because no code implements it.

Organizations that generate governance artifacts soon want to publish them — to dashboards, to internal portals, and increasingly to model clients, so that an engineer's coding assistant can answer "which diagnostic codes can lock verification produce?" from approved documentation rather than from its training data. The natural mechanism is the same protocol this chapter began with: a <span class="ix" data-ix="documentation service">documentation service</span> exposed to model clients as a read-only MCP server, serving exact sections of approved specifications, diagnostic catalogues, and generated artifacts. This is a sound pattern, and it is **[guidance]**: the repository's portal-contract decision record establishes the shape — a declarative, read-only contract describing what each role sees, with the explicit boundary that Nornyx defines the contract and never the portal engine (`docs/decisions/ADR-0012-portal-contract-not-portal-engine.md`) — and the repository's renderers are read-only projections of delivery state that "do not execute work." No MCP server, documentation or otherwise, ships in the repository at the snapshot.

The pattern has one rule that must survive every implementation: the publication layer must never hold <span class="ix" data-ix="normative authority!of documentation">normative authority</span>. It serves *copies* of approved artifacts, derived from the generated outputs of a locked revision; it does not accept edits, does not answer with content that has no source artifact, and is never the place a dispute about what the policy says gets settled — that place is the contract at its revision, as it has been since Chapter 8. The failure mode this rule prevents is quiet and plausible: a convenient service becomes the de facto reference, drifts from its source, and acquires authority by usage. The mitigation is the one this book has used throughout — serve digests alongside content, regenerate rather than edit, and treat any divergence between the service and the locked artifacts as an incident, not a synchronization task. A documentation server is also, structurally, an MCP server, and an organization that stood one up should feed it through Section 27.2's own intake like any other package: the governance layer eats its own cooking or it teaches others not to.

Beyond guidance lies roadmap, and the border needs marking. The contract language tolerates a family of deferred extension blocks — `connectors`, `adapters`, `guardrails`, `capabilities`, `supply_chain`, and others — which the checker accepts without error but which "do not define stable v0.1 runtime behavior" (`nornyx/checker.py:50–62`; `docs/01_LANGUAGE_SPEC_v0_1.md`). A `connectors:` entry can describe an MCP or A2A integration in the older extension style, and an implemented local planner, `nornyx connector-plan`, will validate such declarations — recognizing the protocols, checking capabilities and safe default modes, blocking declared live targets with `CONNECTOR_LIVE_TARGET_DECLARED`, and emitting a report whose safety block records `connectors_enabled: false`, `adapters_executed: false`, `network_used: false` **[implemented]** as validation. But the capability those descriptors describe — live connector interoperation — carries planned status only in the repository's own requirements matrix ("Connector interop … Planned"), and the extension-protocols document that sketches the integration design speaks throughout in "should" [roadmap] (`docs/04_AI_ENGINEERING_REQUIREMENTS_MATRIX.md`; `docs/10_EXTENSION_PROTOCOLS_MCP_A2A.md`). The honest sentence is layered: the descriptors parse today, their validation runs today, and the thing they anticipate does not exist — a sentence whose three clauses carry three different badges, which is precisely why this book uses badges.

> **Assurance boundary.** The eight questions, asked of this chapter's implemented surface. *Guaranteed:* that a scanned package's contents were inventoried and hashed, that the listed detectors ran deterministically over those bytes, that secret-like matches were redacted, that registered contents are hash-locked, and that protocol declarations containing transport or credential material cannot be expressed or generated. *Enforced by:* a local scanner and checker invoked by whoever runs them — nothing forces a scan before adoption except the organization's own pipeline. *Evidence:* the reports, evidence records, and locks, all local files. *Assumptions:* the scan ran against the same bytes that get adopted (the lock is the cross-check), and intake actually routes through this process. *Bypass:* install the package without scanning it; configure the live connector without declaring it. *On failure:* the scanner reports and exits — it blocks nothing by itself. *Tier:* 1 — this is design-time and intake-time governance; the scan gates adoption only where CI makes it a gate. *Unproven:* everything about the package's runtime behavior, which is exactly what the permitted claim declines to assert.

## Summary

Tool protocols create governance surfaces, not governance solutions: MCP standardizes how applications hand tools and context to models, agent-to-agent protocols standardize coordination between peer agents, and both make it dramatically easier to connect an agent to code written by strangers. Two concerns follow and get two mechanisms. Packages are treated as untrusted inert input: a deterministic, local, non-executing scanner inventories and hashes every file, surfaces secrets with hardcoded redaction, detects hooks, protocol-server definitions with broad-filesystem escalation, classified endpoints, dangerous commands, and lifecycle scripts, and cross-checks the package's own claims against observed evidence — while asserting in code that no payload was executed and permitting itself only the claim that a package was inventoried, risk-surfaced, evidence-bound, hash-locked, and approval-gated, never that it is safe. External evidence arrives by import only, from exactly two producers, with anything else refused as an error. Protocol integrations are expressed as contract-only declarations whose schemas admit only `mcp` and `a2a`, pin the execution mode to a constant, and — together with generation-time forbidden-key scanning — make endpoints, credentials, and commands unrepresentable, so a declaration describes an integration boundary without becoming executable configuration. Above the implemented surface sit two labelled layers: a documentation service publishing approved artifacts read-only to model clients is guidance that must never hold normative authority, and the extension descriptors for live connector interoperation parse and validate today while the capability they anticipate remains roadmap.

- A package's self-description is untrusted input; claim-versus-evidence mismatch makes the lie computable.
- "Pass" describes the scan; "critical" describes the package — the scanner reports, the human gates.
- Redaction is hardcoded, not configurable: evidence about secrets must not contain secrets.
- Two importers, import-only; an unsupported evidence producer is an error, not a warning.
- Schema constants plus forbidden-key scanning shut the declaration-to-execution door twice.
- Publication layers serve copies with digests; authority stays with the locked contract.

## Review questions

1. The scan in Listing 27.1 returned `"status": "pass"` and `"risk_tier": "critical"` for the same package. Explain why this is correct behavior, and what would be wrong with a scanner that returned a failing status for risky content.
2. Why does the scanner hardcode redaction of secret-like matches rather than offering a `--show-secrets` flag for authorized reviewers? Connect your answer to the evidence-handling principles of Chapter 11.
3. A vendor's package intake tool reports "no threats detected — package verified safe." Using the permitted-claim discipline of Section 27.2, rewrite that sentence into the strongest claim the tool's actual evidence could support, and list what the original wording asserted beyond it.
4. The protocol-target schema could have made `live_connector_execution` a boolean defaulting to `false`. It is instead a constant. What class of failure does the constant prevent that the default would not, and which chapter's composition rules explain why defaults are the weaker mechanism?
5. An engineer argues the documentation MCP service should also accept correction suggestions from model clients, "since they read it most." Explain which rule of Section 27.5 this violates and what the drift consequence would be.
6. The claim-versus-evidence detector treats README text as `untrusted_claim` even for packages written in-house. Justify this design choice using Chapter 6's authority model.

## Exercises

1. **Scan a real bundle.** Choose a third-party tool package your organization uses or is evaluating — an MCP server is ideal — and run `nornyx package scan` over its unpacked source in a scratch directory. Read all ten Markdown reports. Write the intake memo the Atlas case study implies: findings by severity, claim-versus-evidence results, your accept/constrain/reject recommendation, and — separately — the list of questions the scan *cannot* answer. Do not install or execute anything from the bundle.
2. **Probe the declaration boundary.** Copy `examples/agentic_network_support/support_network.nyx` and attempt to smuggle live material into its protocol target three different ways: an extra field, a forbidden value inside a permitted field, and a change to a schema constant. Record which layer rejects each attempt (block schema, generation-time scan, or check) and the diagnostic produced. Then write two sentences on why defense at two independent layers matters here, referencing Chapter 14.
3. **Design the intake gate.** Section 27.2's flow ends outside the tool: nothing forces a scan. Design the CI arrangement that makes it mandatory for your organization — where the scan runs, what artifact the approval binds to, how the hash lock is checked at deployment, and what happens when a previously approved package publishes a new version. State which tier your arrangement reaches for the intake surface and what would be required to go higher.

## Further reading

- [@mcp-spec] — the protocol itself; read the server capability and tool sections to see precisely what a client trusts a server to describe truthfully.
- [@a2a-spec] — the peer-coordination counterpart; its capability-advertisement model is the input an A2A declaration constrains.
- [@owasp-agentic] — the threat catalogue for agentic systems; its tool-misuse and supply-chain entries motivate every detector in Section 27.2.
- [@nist-scrm] — supply-chain risk-management practice at organizational scale; the frame for making package intake a program rather than a script.
- [@slsa] — supply-chain levels for artifacts; useful for asking what provenance a tool package *could* carry that a scan would then verify rather than infer.
