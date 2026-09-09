# Synthetic Enterprise Extension examples

`alpha-resource-tag` and `beta-priority-policy` are separate standalone Python
projects. They share no source module and declare only the exact
`aps-extension-sdk==1.0.0` runtime dependency. Their values and rules are
synthetic contract fixtures, not manufacturing defaults, customer logic, or a
Production certification.

Run each project or the exact pair through
`scripts/aps_extension_conformance.py`. The conformance tool builds immutable
wheels, checks the SDK hash lock, installs into clean environments, and passes
explicitly materialized objects to APS Runtime. It never scans ambient Python
entry points or creates a Git repository.
