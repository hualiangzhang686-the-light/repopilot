# Contributing

1. Create a focused branch and keep changes tied to one behavior.
2. Add or update a deterministic fixture with an explicit expected result.
3. Run `python -m unittest discover -s tests -v`.
4. Run `repopilot eval --project-root .` and inspect generated changes.
5. Update security boundaries, failure logs, and Trace examples when behavior changes.

Do not add arbitrary shell execution, repository writes outside `SandboxWorkspace`, silent retry loops, fabricated baseline metrics, or model conclusions without verifiable evidence.
