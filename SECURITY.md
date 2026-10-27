# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅        |

## Reporting a vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, report them privately via [GitHub Security Advisories]
(https://github.com/open-winmale/wmshare/security/advisories/new)
("Report a vulnerability"), or contact the maintainers directly.

Please include:

- A description of the issue and its impact;
- Steps to reproduce or a proof of concept;
- Affected version(s) and environment.

## Scope notes

- The SDK sends requests only to the public API endpoints
  (`api.winmale.com` / `test-api.winmale.com`). Any code or document that makes
  the client talk to other hosts should be treated as suspicious and reported.
- Credentials (`client_id` / `client_secret`) are read from environment
  variables, `~/.wmshare/credentials.env`, or explicit constructor arguments.
  Never commit credentials to this repository — `tools/check_leak.py` and CI
  scan for secret-looking literals, but you are responsible for your own keys.

## What is in scope

- Credential leakage or unintended network endpoints in the SDK.
- Injection/unsafe deserialization in catalog or response handling.
- The leak gate itself failing to catch an obvious violation.
