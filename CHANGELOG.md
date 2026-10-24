# Changelog

## 0.3.0

- Refactor CLI, player lookup, data, and projection exception tests so each assertion
  exercises one potentially failing call.
- Refactor the CLI entrypoint warning test to isolate the warning-producing call
  while retaining the exit assertion.
- Validate release tags, distribution metadata, and the installed wheel before
  publishing to PyPI. Manual workflow runs validate without publishing.
- Update package license metadata and add project links for PyPI.

This release retains the existing projection behavior and Python 3.13+ requirement.
