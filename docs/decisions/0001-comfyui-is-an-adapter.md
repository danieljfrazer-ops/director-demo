# ADR 0001: ComfyUI is a generation adapter

- Status: Accepted
- Date: 2026-08-14

## Decision

The project domain, state machine, artifact lineage, and prompt schema will not depend
on ComfyUI node IDs. ComfyUI workflows are versioned adapter assets with explicit
semantic bindings. Native engines may implement the same generation contracts.

## Consequences

This adds an adapter layer and compatibility tests, but protects projects from node
renumbering, custom-node churn, engine changes, and platform-specific failures.
