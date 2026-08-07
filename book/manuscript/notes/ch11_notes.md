# Chapter 11 — Author Notes

## Claims I could NOT verify (and what I wrote instead)

1. **Evidence retention / lifecycle management.** No repository facility stores, expires, or manages
   evidence over time. I did not attribute any retention capability to the toolchain; the chapter says
   plainly that "Retention itself is outside the governance layer: nothing in the toolchain stores,
   expires, or manages evidence over time." Section 11.6's four minimization techniques are presented
   as general design guidance, not as implemented behavior.
2. **"Audit-package assembly" contents.** Fact pack 02 §1 records that `scripts/agentic_network_ci.py`
   performs audit-package assembly as one of its fourteen steps, but the script was not executed in
   this authoring pass and I did not read its assembly step line by line. I therefore described it only
   as "a pipeline step rather than a command" and deferred the design treatment to Chapter 36. No claim
   is made about the bundle's exact file list.
3. **Adapter version "0.2.0" as an evidence-record value.** Section 11.2's sentence "produced by an
   in-process cooperative adapter, version 0.2.0" is illustrative prose about what a producer field
   *should* say, not a quotation of a real record. The adapters package version 0.2.0 appears in
   ADR-0040 and the CHANGELOG prose; fact pack 02 §13 flags the published wheel as unaudited, so I did
   not present it as a verified record value.
4. **Syft/gitleaks importer version fields.** `parse_syft_report` reads a `descriptor.version` from the
   report when present; `parse_gitleaks_report` does not populate `source_version`. The chapter's
   general rule ("they should carry the source tool and, where available, its version") is stated as
   design guidance and the Nornyx callout does not claim version capture for both importers.
5. **Atlas evidence stream contents.** The four-record stream in the Atlas case-study callout is
   fictional case-study material consistent with the case bible and the real 18-type event set. The
   revision `git:9f3c1a7…` follows the bible's shortened-SHA convention; it is not a repository value.

## PROPOSED-REF additions

None. Every citation used ([@otel], [@sre-book], [@in-toto], [@sigstore], [@iso-27001], [@eu-ai-act],
[@slsa], [@nist-ai-rmf], [@merkle] indirectly via Chapter 12 cross-reference) is a canonical key.

## Repository paths I personally verified

- `/home/user/nornyx/nornyx/agentic_evidence.py` — read lines 60–95 (`_SUCCESS_TERMINALS`,
  `_FAILURE_TERMINALS`, `LIMITATIONS`) and 380–425 (replay fingerprint). The three `LIMITATIONS`
  sentences quoted in Listing 11.2 and Section 11.4 are verbatim from lines 88–92.
- `/home/user/nornyx/nornyx/cli.py` — read `cmd_package_evidence_import` (lines 303–346). Confirmed
  the parser map is exactly `{"syft": parse_syft_report, "gitleaks": parse_gitleaks_report}` and that
  any other tool returns code `UNSUPPORTED_EVIDENCE_TOOL` with exit 1.
- `/home/user/nornyx/nornyx/package_scanner.py` — read `evidence_record` (244–290), `parse_syft_report`
  and `parse_gitleaks_report` (749–814), `ADAPTER_PARSERS` (817–820), and the adapter-execution status
  block (895–936). Confirmed: `source` ∈ {`built_in_scanner`, `external_adapter`}; `status` ∈
  {`observed`, `imported`}; the `unavailable` detail string "external tools are not executed
  automatically; provide report_path to import evidence"; the appended "command is available but not
  executed by Nornyx"; `REDACTED_SECRET_LIKE_VALUE` on gitleaks imports; `REQUIRED_ADAPTER_UNAVAILABLE`
  producing an error-level diagnostic and `status: fail`.
- `/home/user/nornyx/docs/agentic-network/06_RUNTIME_EVIDENCE.md` — read in full. Source of Listing 11.1
  (the `evidence-validate` invocation) and of the "no daemon, listener, webhook, queue consumer, or
  telemetry collector — inputs are local files" framing used in the listing caption.
- `/home/user/nornyx/docs/decisions/ADR-0040-governance-assurance-tiers.md` — read in full. Source of
  "the event producer is self-declared" and of the statement that `input_digest`/`output_digest` are
  not semantically verified against any actual runtime payload.

Facts taken from the fact packs without independent re-verification (all carry repository paths there):
the `producer.type` three-value enum and `evidence_artifact` path-containment behavior
(`schemas/agentic_runtime_events_v1.schema.json`, fact pack 02 §5.1/§5.2); the report `safety` block
(fact pack 02 §5.2); the scanner redaction invariants (fact pack 04 §1.4); the fourteen-step reference
CI (fact pack 02 §1, doc 11).
