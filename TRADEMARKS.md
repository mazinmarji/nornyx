# Nornyx Project Identity

> **Status: draft policy, not a legal instrument.** Subject to independent
> trademark/IP counsel review before being treated as an enforcement
> instrument. It records the project's intent and its current factual position.
> It does not create rights, and it does not assert rights the project has not
> obtained.

## The software license is not the project's name

Nornyx is [MIT licensed](LICENSE), and that is not changing. You may use, copy,
modify, merge, publish, distribute, sublicense, and sell the software,
including for commercial purposes, subject only to the MIT notice condition.
Forking is a legitimate use of that license. Nothing here narrows it.

Copyright licensing and project identity are different things:

| | Covers | Governed by |
| --- | --- | --- |
| **Copyright** | the source code and its derivatives | [LICENSE](LICENSE) (MIT) |
| **Project identity** | the name that tells people whose project this is | this document |

The MIT license transfers copyright permissions. It does not, by itself, grant
permission to present a modified or independent work as an official Nornyx
release, or as endorsed or certified by this project. Those are statements
about origin, and a statement about origin can be false in a way that a code
change cannot.

## Current factual position

**No trademark registration is claimed or asserted anywhere in this
repository.** The project uses "Nornyx" as an unregistered project name. The
registered-trademark symbol is deliberately absent from this repository, and
using it without registration would itself be a misrepresentation in several
jurisdictions.

Whether registration is pursued, in which jurisdictions and classes, and by
which owning entity are open questions requiring counsel. Until then, this
document describes intent and accurate description — not enforceable
restriction. See [Actions this document cannot
perform](#actions-this-document-cannot-perform).

## Descriptive use, which is welcome

You do not need permission to describe what your software actually does. All of
these are accurate and encouraged where true:

- "Based on Nornyx."
- "Forked from Nornyx."
- "Compatible with the Nornyx `.nyx` contract language" — where the
  compatibility claim is actually satisfied. See
  [`docs/NYX_FORMAT_AND_CONFORMANCE.md`](docs/NYX_FORMAT_AND_CONFORMANCE.md)
  for what each claim requires.
- "Implements the Nornyx governance contract semantics."
- "Works with Nornyx."
- Attribution to the Nornyx project, including the MIT notice you are already
  required to retain.

Naming the project in order to say something true about it is nominative use.
It is exactly what a project name is for.

## Representations that would be misleading

The concern is not that you used the name. It is that a reader would be misled
about who produced something, or about what has been verified. Absent
authorization from the project, please do not present software as:

- an **official Nornyx release** or an official Nornyx product, when it was not
  published by this project;
- **endorsed by**, **approved by**, or **affiliated with** the Nornyx project,
  when there is no such relationship;
- **certified** or **conformance-tested by** Nornyx. This project operates no
  certification authority and issues no certification, so no such certification
  exists to claim — see
  [`docs/NYX_FORMAT_AND_CONFORMANCE.md`](docs/NYX_FORMAT_AND_CONFORMANCE.md);
- **Nornyx-conformant**, where the semantics have in fact been changed. Renaming
  is fine; misdescribing behaviour is the problem.

The distinguishing test is simple: *would a reasonable reader think this came
from, or was checked by, the Nornyx project when it was not?*

## Forks

Forks are expected and permitted. Two suggestions, offered as guidance rather
than as conditions on the license:

1. **A materially modified distribution reads better under its own name.** If
   you have changed semantics, defaults, or scope, your users are better served
   by a distinct product identity — and so are Nornyx's, who will otherwise
   file your bugs here. Retain the MIT attribution you are required to retain
   and describe the lineage plainly: "derived from Nornyx."

2. **Renaming the file extension is your call.** `.nyx` is Nornyx's canonical
   extension, and this project makes no claim that anyone is forbidden to name a
   file `.nyx`. The parser does not gate on the extension and will not start
   doing so. What matters is the semantic claim attached to the format, not the
   characters after the dot.

A fork that renames everything and claims nothing about Nornyx raises no issue
under this document at all.

## Logos

The project has no distinct logo at present. If one is adopted, its use will be
addressed here rather than assumed to follow from the code license.

## Actions this document cannot perform

Recorded here so the boundary is not misread. A repository file cannot:

- register a trademark, in any jurisdiction;
- establish common-law rights beyond whatever actual use has already
  established;
- create a contractual restriction on MIT licensees;
- substitute for a trademark clearance search or a legal opinion;
- bind any third party who never agreed to it.

Its function is to state the project's position clearly and consistently, so
that the position is documented from a known date, and so that anyone acting in
good faith can tell what is accurate to say.

## Questions

Open an issue at <https://github.com/mazinmarji/nornyx/issues>. Uses not
described here are not thereby forbidden — most likely they simply have not
come up yet, and asking is welcome.
