# Security Policy

Thank you for helping keep Backcaster and its users safe.

## Supported Versions

Security fixes are applied to the latest code on the default branch.

| Version | Supported |
| --- | --- |
| Default branch (`main`) | ✅ |
| Older branches / historical snapshots | ❌ |

If you are running Backcaster from an older commit, please upgrade to the latest `main` branch before reporting an issue.

## Reporting a Vulnerability

Please **do not** open public GitHub issues for suspected vulnerabilities.

Instead, report vulnerabilities privately by emailing:

- **commuted.convicted@gmail.com**

Please include:

1. A clear description of the issue and potential impact.
2. Steps to reproduce (proof-of-concept code is helpful).
3. Affected environment details (OS, Python version, dependency versions).
4. Any suggested remediation if you have one.

## Response Expectations

- **Initial acknowledgement:** within **3 business days**.
- **Status updates:** at least every **7 business days** while triaging/fixing.
- **Target remediation window:**
  - Critical/High severity: within **14 days** when feasible.
  - Medium/Low severity: next planned release cycle.

These windows are goals, not guarantees, and may vary based on complexity and operational risk.

## Coordinated Disclosure

We support coordinated disclosure and request that reporters:

- Give us reasonable time to investigate and deploy a fix before public disclosure.
- Avoid accessing or modifying data that does not belong to you.
- Avoid denial-of-service, destructive testing, or social engineering.

After a fix is available, we will coordinate disclosure timing and attribution with the reporter when possible.

## Scope

This policy covers:

- Source code in this repository.
- First-party scripts and workflows maintained here.

This policy does **not** cover:

- Third-party services or dependencies outside this repository.
- Misconfigurations in downstream deployments not maintained by this project.
