# __PROJECT_ID__

Owner: `__OWNER__`

Repository: `__REPOSITORY_URL__`
License expression: `__LICENSE_EXPRESSION__`

This standalone project targets APS Extension SDK `1.0.0` and APS Runtime
`0.1.0`. It contains no APS Core source. The Developer Kit value remains
`0.0.0-not-published` until TASK-P8-15 publishes a verified kit combination.

Use the repository-side conformance command supplied with the matching tooling
set; do not install from `latest`, copy `backend/app`, scan global entry points,
or select code from an HTTP request.

```shell
python scripts/aps_extension_conformance.py check \
  --project path/to/this/project \
  --output build/enterprise-extension
```

The starter implementation is deliberately synthetic: a generic resource-tag
Constraint and an independently implemented Validation Rule. Replace the
business semantics and fixtures under enterprise ownership, keep the public SDK
imports and manifest pair, and rerun conformance before packaging.
