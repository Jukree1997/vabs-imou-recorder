# Security Policy

## Sensitive information

Do not open a public issue or commit files containing:

- IMOU App IDs paired with App Secrets
- access tokens, refresh tokens, or signed API requests
- camera serial numbers, QR codes, passwords, or security codes
- customer identity, location, or recorded video

If a credential is exposed, revoke or rotate it immediately in the relevant
IMOU or infrastructure console and remove it from Git history before pushing.

## Reporting a vulnerability

Report vulnerabilities privately to the repository owner. Do not include live
credentials, recorded footage, or customer information in the report. A secure
transfer method should be agreed before sharing diagnostic artifacts.

