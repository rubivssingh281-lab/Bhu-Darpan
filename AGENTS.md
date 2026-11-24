# Bhu-Darpan AI Agent Execution & CI Master Rules

This file governs the behavior of AI assistants (Antigravity, Claude Code, Gemini CLI, Cursor) in this repository.

## 🚨 MANDATORY CI VERIFICATION PROTOCOL (NEVER-FAIL-PUSH GATE)

Whenever committing or pushing code in this repository, you **MUST ALWAYS** follow this two-stage verification process:

### Stage 1: Pre-Push Local Replication (Before `git push`)
Ensure the local environment matches GitHub Actions `.github/workflows/ci.yml` exactly. Run:
```powershell
# 1. Whitespace & merge conflict check
git diff --check

# 2. Syntax, flake8 & ruff validation (avoids undefined name errors like F821)
Backend\.venv\Scripts\ruff.exe check Backend/app --ignore I001

# 3. Bytecode compilation audit
Backend\.venv\Scripts\python.exe -m compileall -q Backend/app Backend/tests

# 4. Pipeline regression verification
Backend\.venv\Scripts\python.exe Backend/tests/selftest.py
Backend\.venv\Scripts\python.exe Backend/tests/test_carbon_biomass.py
```
*Note: A local hook at `.git/hooks/pre-push` prevents pushing if any of these checks fail.*

---

### Stage 2: Post-Push Remote Run Status Check (After `git push`)
Immediately after pushing to remote, execute:
```powershell
Backend\.venv\Scripts\python.exe scripts/check_remote_ci.py
```
**Verification Requirements**:
- Polls the GitHub Actions REST API for the latest commit SHA.
- Confirms the workflow status reaches `status: completed` and `conclusion: success`.
- If the workflow run reports `conclusion: failure`, immediately inspect the failing step, inform the user with root-cause analysis, and deploy an immediate hotfix.
