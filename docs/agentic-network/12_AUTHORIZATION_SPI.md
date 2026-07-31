# Authorization SPI

`nornyx.agentic` SPI 1.2 adds an additive construction-state capability to the
existing `Authorizer` returned by `load_authorizer`:

```python
from nornyx.agentic import load_authorizer

authorizer = load_authorizer(
    "network.nyx",
    "nornyx.agentic_network.lock",
    validation_as_of="2026-07-31T00:00:00Z",
)
state = authorizer.state
```

`authorizer.state` is the same `AuthorizerState` instance on every access. It
represents the three inputs retained by that Authorizer after the load path has
validated the contract, composed effective governance, and verified the lock:

- `state.document` returns the validated contract as a detached plain
  `dict`/`list` graph;
- `state.composition` returns a detached public `CompositionResult`;
- `state.lock_payload` returns the verified lock as a detached plain
  `dict`/`list` graph;
- `state.contract_digest` and `state.network_lock_digest` are the exact digest
  values exposed by the Authorizer.

The returned views are new detached copies. Mutating any depth of one view does
not change a later view, an authorization decision, or either digest. The
retained graph shared by `Authorizer` and `AuthorizerState` is recursively
frozen. State access performs no file read, governance composition, lock
verification, network access, or framework import. Changing or deleting the
source files after `load_authorizer` returns cannot change the state.

`CompositionResult` is deliberate on this SPI: it is already a public
`nornyx.governance` type and is required by existing artifact and evidence
validators. Returning a detached instance preserves those public APIs without
promoting a private authorization-engine type. A compatibility or evidence
consumer can therefore stay entirely on public surfaces:

```python
from nornyx.agentic import validate_runtime_events

report = validate_runtime_events(
    state.document,
    state.composition,
    state.lock_payload,
    events_payload,
)
```

The `Authorizer(...)` constructor remains available for source compatibility,
but it does not itself read, validate, compose, or verify files. Consumers that
need the authoritative validated and lock-verified guarantee must obtain the
Authorizer through `load_authorizer(...)`.

This is a read-only SPI capability. It changes no authorization, evidence,
schema, occurrence, replay, approval, or runtime semantics and adds no
framework-specific behavior.
