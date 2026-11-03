# Contributing to Bhū-Darpan

Thank you for your interest in contributing to **Bhū-Darpan**!

## Development Workflow

1. **Fork and Branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Environment Setup**:
   ```bash
   cd Backend
   python3.12 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Running Tests**:
   ```bash
   pytest tests/ -v
   ```

4. **Code Quality**:
   - Follow PEP 8 guidelines.
   - Run `ruff check Backend/app` before committing.

5. **Submitting Changes**:
   - Use conventional commit messages (`feat: ...`, `fix: ...`, `docs: ...`).
   - Open a pull request against the `main` branch.
