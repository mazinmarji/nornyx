# Historical example contracts

These five `.nyx` files are early design-era showcase artifacts written in a
pre-v0.1 block syntax. They do not parse under the current checker
(`nornyx check` reports errors by design) and are retained unchanged as
historical records only.

They are deliberately excluded from the governance compatibility corpus
(`tests/fixtures/governance_compatibility/manifest.json`), which tracks the
current top-level `examples/*.nyx` surface.

For working examples of the current language, use the top-level files in
[`examples/`](..) or run `nornyx examples` to copy the bundled set.
