# RFC-0001: Nornyx Core Language

## Problem

AI-assisted software engineering lacks a common executable control layer for context, agents, skills, policies, evals, harnesses, approvals, traces, and evidence.

## Proposal

Define Nornyx v0.1 as a YAML-compatible source format and CLI for checking/generating AI-engineering artifacts.

## Core blocks

- project
- constitution
- intent
- context
- agent
- skill
- policy
- harness
- eval
- trace
- evidence
- approval
- budget

## Out of scope

- native compilation;
- autonomous deployment;
- arbitrary shell execution;
- production self-healing;
- full package registry.
