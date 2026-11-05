# Contributing to Bhū-Darpan

Thank you for your interest in contributing to **Bhū-Darpan**! We welcome bug fixes, documentation improvements, and feature contributions.

## Branch Naming Conventions
Follow standard prefix conventions for clear branch identification:
- `feat/<topic>`: New functionality or analytical capabilities
- `fix/<issue>`: Bug resolutions or defect corrections
- `docs/<topic>`: Documentation additions or architectural revisions
- `chore/<task>`: Tooling, dependency, or configuration updates

## Development Workflow

1. **Fork and Branch**:
   ```bash
   git checkout -b feat/your-feature-name
   ```

2. **Environment Setup**:
   ```bash
   cd Backend
   python3.12 -m venv .venv
   source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Running the Test Suite**:
   ```bash
   pytest Backend/tests/ -v
   ```

4. **Code Quality & Linting**:
   - Adhere strictly to PEP 8 standards.
   - Run the fast linter before submitting commits:
     ```bash
     ruff check Backend/app
     ruff format Backend/app
     ```

## Pull Request Checklist
Before opening a pull request against `main`, ensure that:
- [ ] Automated tests pass (`pytest Backend/tests/ -v`).
- [ ] Ruff checks pass with zero errors (`ruff check Backend/app`).
- [ ] Commit messages follow the Conventional Commits specification (`feat:`, `fix:`, `docs:`, `chore:`).
- [ ] Documentation is updated for any modified API endpoints or configuration parameters.
