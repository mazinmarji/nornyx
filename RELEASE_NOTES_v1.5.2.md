## Nornyx 1.5.2

`pip install --upgrade nornyx`

Nornyx 1.5.2 completes the explicit-profile symlink hardening introduced in
1.5.1.

### Complete ancestor symlink enforcement

`nornyx profiles validate` and `nornyx init --profile-path` now define their
symlink-inspection trust root independently from the pack's immediate parent.
The governance loader checks every unresolved path component from that trust
root through the requested pack before calling `resolve()` or `realpath()`.
Components followed by `..` remain visible to this inspection.

This closes the remaining case where a higher ancestor, such as `link_root` in
`link_root/profiles/profile.yaml`, was itself a symlink. Direct pack-file and
immediate-directory symlinks remain rejected as before.

The Nornyx language/schema version remains 1.0. This patch does not change
built-in profiles, starter output, approval semantics, or runtime rule
evaluation.

**Full changelog:** https://github.com/mazinmarji/nornyx/blob/main/CHANGELOG.md
