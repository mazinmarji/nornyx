# External Evaluation Evidence

Nornyx complements evaluation tools; it does not run them and does not
replace Promptfoo, LangSmith, or observability platforms.

## Flow

1. Your evaluation tool produces a results file (for Promptfoo:
   `promptfoo eval --output results.json`). Nornyx never executes the tool.
2. Import the results into the local format `eval-run` consumes:

   ```text
   nornyx eval-import promptfoo examples/agentic_network_support/eval/promptfoo_results.json --eval-name support_response_quality --subject-revision git:feedfacefeedfacefeedfacefeedfacefeedface --out dist/imported_eval_results.json
   ```

   The importer validates the report shape, aggregates `namedScores` and the
   pass rate, records the producer and report version, and binds the
   normalized output to the report artifact's SHA-256 and the declared
   subject revision. Malformed or mismatched reports are rejected with
   `EVAL_IMPORT_ERROR`.

3. Validate the declared thresholds and dataset integrity:

   ```text
   nornyx eval-run examples/agentic_network_support/support_network.nyx --results dist/imported_eval_results.json --repo examples/agentic_network_support --strict
   ```

   `eval-run` hashes declared datasets and holdouts, checks holdout/train
   overlap, and evaluates each metric threshold declared in the contract's
   `evals` block.

4. The result becomes part of the revision-bound governance evidence: the
   support example's `governance_evidence` block carries a
   `support_eval_report` record whose `content_hash` and `subject_revision`
   bind the evaluation evidence to the exact contract revision.

5. Human approval is accepted only for the exact evaluated revision: the
   `agentic_network_authority` approval is revision-bound
   (`revision_binding.exact: true`) and expires (`expires_after: P7D`).

6. A contract or prompt change invalidates stale approval or evidence: any
   change to `agentic_network.subject_revision` without re-binding every
   record fails with `AN_REVISION_MISMATCH`, and the network lock fails with
   `AN_LOCK_SOURCE_STALE`.

## Honest limits

Nornyx validates supplied metrics against declared thresholds and binds the
report bytes. It cannot verify that the evaluation was actually run, that the
metrics are honest, or that the dataset was appropriate — hash validity
proves content binding, not truth.
