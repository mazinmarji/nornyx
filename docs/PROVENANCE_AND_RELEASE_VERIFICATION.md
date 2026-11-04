# Provenance and Release Verification

**Authoritative** for how an artifact is shown to have come from this project.
Decision record:
[ADR-0045](decisions/ADR-0045-project-identity-conformance-and-provenance.md).
For what makes something a Nornyx contract, see
[`NYX_FORMAT_AND_CONFORMANCE.md`](NYX_FORMAT_AND_CONFORMANCE.md).

## 1. Provenance and conformance are independent

They answer different questions, and collapsing them is the mistake this
document exists to prevent.

- **Provenance** — *did this come from the Nornyx project?*
- **Conformance** — *does this behave according to the Nornyx specification?*

All four combinations are real and legitimate:

| | **Conformant** | **Nonconformant** |
| --- | --- | --- |
| **Official** | An official Nornyx release that passes the corpora. The ordinary case. | An official release with a genuine bug. Authentic and wrong at the same time. |
| **Unofficial** | An independent implementation that correctly implements Nornyx. **This is a goal of the project, not a threat to it.** | A fork with changed semantics. Legitimate to ship; not legitimate to describe as Nornyx-conformant. |

An authentic *old* release is a fourth state worth naming: official, historical,
and possibly superseded. Provenance verifying does not mean current.

Two rules follow, and they run in both directions:

> **Official provenance is never a substitute for conformance testing.**
> **Conformance never implies Nornyx endorsement.**

## 2. What Nornyx already binds — and what it deliberately does not

Nornyx has strong content-binding primitives. Understanding what they do
prevents expecting origin proof from something that never claimed to offer it.

| Primitive | Binds | Where |
| --- | --- | --- |
| `contract_digest()` | canonical governed content of a parsed contract | `nornyx/agentic_artifacts.py` |
| Network lock | contract digest, subject revision, record digests, artifact SHA-256s | `nornyx.agentic_network_lock.v1` |
| Generation manifest | generated artifact set and its hashes | `nornyx.agentic_generation_manifest.v1` |
| `subject_revision` | an immutable content-addressed revision | validated at lock time |
| Runtime-event binding | `network_id`, `contract_digest`, `network_lock_digest`, `subject_revision` | `nornyx.agentic_runtime_events.v1` |

Every one of these binds **content**. None of them binds **producer identity**,
and that is by design — `nornyx/agentic_artifacts.py` says so in its own module
docstring: the lock "never attests runtime behavior, producer identity, or
truth."

This is why provenance is **detached**. Putting a producer identity inside the
lock would make lock bytes vary by producer and destroy the byte-stability that
makes locks reviewable and diffable. Provenance rides alongside the artifact,
never inside the governed payload.

```
governed .nyx source
      ↓
canonical representation        ← contract_digest()
      ↓
generated artifact / release    ← generation manifest, lock
      ↓
provenance statement            ← detached, alongside
      ↓
cryptographic signature         ← standards-based (PEP 740 / Sigstore)
      ↓
independent verification        ← artifact + public trust material + local verifier
```

## 3. How official Nornyx releases are produced

Four properties of the current pipeline, each verifiable from the repository:

1. **Trusted Publishing (OIDC), no stored token.** PyPI verifies the OIDC
   identity of the publishing workflow. There is no API token anywhere to
   leak. See [`../.github/workflows/release.yml`](../.github/workflows/release.yml).
2. **A positive tag gate, bound to the package version and to `main`.**
   Publishing fires only when a GitHub Release is published *and* its tag matches `^v[0-9]+\.[0-9]+\.[0-9]+$` exactly. Any
   other tag shape — an adapter tag, a prerelease suffix, an unrelated tag — is
   excluded rather than merely "not matched". The tag's `X.Y.Z` must also
   equal the `pyproject.toml` version at the commit the tag targets, so a
   well-formed tag on a commit that declares a different version publishes
   nothing, and the publish job uploads only the sdist and wheel for that
   version. A release marked as a prerelease publishes nothing, and `main`
   must contain the tagged commit. GitHub runs a release with the workflow
   files of the tagged commit, so these checks apply to tags on commits that
   include them; a tag on an older commit, or on a branch whose workflows
   differ, runs that commit's own gate.
3. **CI builds the artifact, not a human.** `RELEASING.md` forbids
   `twine upload` by hand, so the published artifact corresponds to the tagged
   source.
4. **Exact-candidate identity in CI.** Jobs assert
   `git rev-parse HEAD` equals the PR head SHA before testing, so results
   belong to the exact reviewed revision.

## 4. Verifying an artifact yourself

No Nornyx service is contacted. Everything below runs against PyPI, GitHub, and
your local machine.

### Step 1 — What was actually installed

Version metadata proves only what a distribution *calls itself*. To establish
which bytes arrived and from where, use pip's own installation report:

```bash
pip install --report report.json --dry-run "nornyx==1.11.0"
```

The report records, per resolved requirement, the download URL and the archive
SHA-256. The repository ships a worked parser for exactly this in
[`../examples/pip_only_conformance/provenance.py`](../examples/pip_only_conformance/provenance.py),
which distinguishes wheel from sdist, checks the serving host, and treats a
missing entry as a provenance *failure* rather than as success.

### Step 2 — Whether a PyPI attestation exists, and whether it verifies

PyPI serves PEP 740 attestations through its Integrity API, one provenance
object per file. Ask it, rather than assuming:

```bash
curl -s -w '\nHTTP %{http_code}\n' -H "Accept: application/vnd.pypi.integrity.v1+json" https://pypi.org/integrity/nornyx/1.12.0/nornyx-1.12.0-py3-none-any.whl/provenance
```

HTTP 200 returns a provenance object that names the publisher (repository,
workflow, and the environment PyPI recorded) and carries the attestation
bundles. HTTP 404 with the JSON body
`{"message":"No provenance available for <file>"}` means the file exists and
no attestation was published for it: **absent** in [§6](#6-what-absence-of-provenance-means--and-does-not),
not a verification failure. Any other 404, such as an HTML page, means the
version or file name is wrong; correct it rather than recording absence. The
PyPI JSON API (`/pypi/<project>/<version>/json`) has no provenance field at
all, so it cannot answer this question either way.

That an attestation exists does not show that it verifies. PyPA's
`pypi-attestations` tool (`pip install pypi-attestations`) downloads the file
and checks its attestations against the Sigstore trust root, the publishing
repository and its workflow:

```bash
pypi-attestations verify pypi --repository https://github.com/mazinmarji/nornyx pypi:nornyx-1.12.0-py3-none-any.whl
```

`OK` is **verified**. Once network and certificate-store problems are ruled
out, an error for a file that has a provenance object is **failed**, never
**absent**.

### Step 3 — Tag, commit, and source

```bash
git verify-tag v1.11.0 2>&1 || echo "no signature on tag (see §5)"
git rev-parse v1.11.0^{commit}
```

The tag resolves to an immutable commit SHA, which is the source the release
workflow built from. The one exception among published releases, 1.1.9, is
recorded in §5.

## 5. Current status, stated plainly

Verified on 2026-11-04 through the PyPI Integrity API and
`pypi-attestations verify pypi`, file by file, as in [§4 Step 2](#step-2--whether-a-pypi-attestation-exists-and-whether-it-verifies):

- **Every published distribution carries a PEP 740 attestation that
  verifies.** Both files of every `nornyx` release from 1.1.9 through 1.12.0
  (30 files) carry an attestation signed for this repository's `release.yml`,
  which PyPI records as published from the `pypi` environment, and both files
  of every `nornyx-agentic-adapters` release from 0.2.0 through 0.3.1 (6
  files) one signed for `adapters-release.yml`, recorded from
  `pypi-adapters`. Each verifies. The environment comes from PyPI's publisher
  record, not from the signed certificate. Releases before `nornyx` 1.12.0 and
  `nornyx-agentic-adapters` 0.3.1 received their attestations from the publish
  action's default; from those releases both workflows declare
  `attestations: true` explicitly, so attestation no longer depends on a
  default the project does not control. A later release is not covered by
  this statement until it is verified the same way.
- **1.1.9 was not built from its tag.** Its signing certificates record a
  manual (`workflow_dispatch`) run of `release.yml` on `main` at `8fcdf0c`,
  the commit that added that workflow, not tag `v1.1.9` (`c864429`). Every
  other published file's certificate names its release tag.
- *Correction (2026-11-04).* Until this date this section said that published
  nornyx distributions carried no PEP 740 attestation and that both files of
  `nornyx==1.11.0` reported `provenance: null`, verified on 2026-09-01 against
  the PyPI JSON API. That was wrong. The JSON API has no provenance field, so
  the command used then reported nothing for every file, attested or not.
  PyPI accepts attestations only with the upload, so the files published
  before 2026-09-01 carried them then as well. The method in Step 2 replaces
  that command.
- **Git tags are not currently signed**, so `git verify-tag` will report no
  signature. Tag signing is a maintainer-key decision, not a repository change.
- **GitHub build attestations (`actions/attest-build-provenance`) are not
  used.** For the PyPI distribution they would largely duplicate PEP 740 over
  the same artifact; adding a second mechanism was considered and deferred
  rather than adopted for completeness.

Stating this is the point. A verification path that reports what is actually
there is worth more than one that asserts what ought to be.

## 6. What absence of provenance means — and does not

This distinction is mandatory, and tooling that blurs it is wrong.

| Result | Meaning | What it does **not** mean |
| --- | --- | --- |
| **Verified** | The artifact carries provenance and it checks out against public trust material. | That the artifact is conformant, current, or bug-free. |
| **Absent** | No provenance was supplied. | That the artifact is invalid, malicious, or semantically wrong. Ordinary MIT software has no provenance and works fine. |
| **Failed** | Provenance was supplied and did not verify. | Nothing benign. This is the state that warrants alarm — and it is why it must never be reported as "absent". |

Three consequences:

- **Stripping provenance is permitted.** MIT allows redistribution. Removing
  provenance leaves working software; it removes only the ability to *prove*
  project origin. Nothing in Nornyx detects, punishes, or degrades on removal,
  and nothing will — that would be DRM, which
  [ADR-0045](decisions/ADR-0045-project-identity-conformance-and-provenance.md)
  rejects.
- **Modifying signed material invalidates the signature, not the software.**
  A modified artifact fails verification and keeps running. Verification tells
  you what you can prove; it is not an enforcement mechanism and must not be
  built into one.
- **A declaration is not proof.** A field reading `official: true`, a vendored
  string, or a README badge establishes nothing. Only a mechanism a third party
  can independently reproduce substantiates an origin claim. Any Nornyx tooling
  that reports provenance must fail closed on the claim while leaving the
  software usable.

## 7. Threats this addresses, and what remains

| Threat | Response | Residual |
| --- | --- | --- |
| Straight clone republished elsewhere | MIT attribution survives; repository history and release provenance still identify origin; the clone cannot mint future official signatures. | Attribution removal requires enforcement, which is legal, not technical. |
| Cosmetic rename (`Nornyx`→`X`, `.nyx`→`.abc`) | Permitted. It is simply no longer an official Nornyx distribution, and modified artifacts cannot retain valid project provenance. | None — this is a supported outcome, not a defended-against one. |
| Independent reimplementation of the semantics | Not defended against, by design. The project competes on specification authority, conformance corpora, and ecosystem adoption. | Real and accepted. A copyright monopoly over concepts is not available and is not sought. |
| False "official Nornyx" claim | Provenance verification, [`../TRADEMARKS.md`](../TRADEMARKS.md), and this document's verification path. | Depends on trademark posture, which requires counsel. |
| False conformance claim | The scoped-claim requirements in [`NYX_FORMAT_AND_CONFORMANCE.md`](NYX_FORMAT_AND_CONFORMANCE.md) and deterministic corpora. | No purpose-built third-party language conformance suite yet. |
| Provenance stripping | Reported as *absent*, distinctly from *failed*; software keeps working. | Cannot be prevented, and preventing it is not a goal. |
| Forged `official: true` field | Declarations carry no weight; only reproducible verification does. | Requires consumers to actually verify. |

## 8. Constraints on any future signing work

Recorded so a later change does not quietly violate them:

- **Do not invent Nornyx cryptography.** Use PEP 740, Sigstore, or the signing
  primitives the packaging ecosystem already provides. Nornyx owns the
  semantics of what is attested, not the transport.
- **Verification must never require a Nornyx-operated service.** Once the
  artifact, its attestation bundle, and the required trust material have been
  obtained, the cryptographic check itself must be performable locally where
  the mechanism supports it. Obtaining those inputs normally means reaching a
  package index or forge — that is expected and is not a Nornyx dependency.
  Any design requiring a live Nornyx endpoint at check time is rejected on
  vendor-neutrality grounds.
- **No phone-home, no license server, no machine binding, no runtime origin
  check.**
- **Never alter the governed payload to carry provenance.** Detached only.
  Provenance that moves a governed digest breaks exact-revision semantics.
- **Key compromise is the real residual risk** once signing is live. A signing
  key that can mint official provenance is a higher-value target than any
  credential the project holds today, and adopting one requires a rotation and
  revocation plan before it is adopted, not after.
