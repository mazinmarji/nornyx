# Nornyx Optional Portal Contract Extension

## Purpose

The Portal Contract Extension makes Nornyx easy to render into project dashboards without turning Nornyx into a portal framework.

It helps developers build:

```text
Developer PMO Portal
Governed Delivery Control Plane portal
company engineering dashboard
VS Code side panel
terminal dashboard
Markdown/HTML project report
CI summary
```

## What the extension defines

```text
portal_contract
role_view
dashboard_section
widget_hint
data_source
render_target
integration_target
```

## What it does not define

```text
frontend framework
authentication
database
ticketing workflow engine
production controls
deployment system
runtime actions
```

## Example

```nyx
portal_contract NornyxPortal:
    source: delivery_state

    role_view Developer:
        sees:
            - assigned_goals
            - validation_commands
            - pending_evidence
            - failing_checks

    role_view Architect:
        sees:
            - architecture_decisions
            - design_risks
            - dependency_boundaries
            - pending_reviews

    role_view PMO:
        sees:
            - roadmap
            - goal_completion
            - risks
            - evidence
            - next_actions

    render_targets:
        - shell
        - markdown
        - json
        - developer_pmo_portal
        - ide_panel
```

## Best-practice rule

The contract defines what a role should see, not how the UI must be implemented.

## Safety

All generated portal artifacts should be read-only by default.

Any future write action must go through explicit Nornyx policy, capability, approval, trace, and evidence gates.
