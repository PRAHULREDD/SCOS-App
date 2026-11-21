# Contributing to SCOS

Thank you for considering contributing to the **Smart Waste Collection and Management System (SCOS)**! This guide outlines how to set up your environment, contribute code, run tests, and submit pull requests.

For an overview of the system architecture and project scope, please review the [README.md](README.md).

---

## Getting Started

1. **Check existing issues and discussions:** Before starting substantial work, open an issue or check existing tickets to discuss proposed changes or bug fixes.
2. **Review project boundaries:** SCOS focuses strictly on its three designated roles (`CITIZEN`, `ADMIN`, `DRIVER`). Changes should preserve existing workflow semantics and security controls.

---

## Development Workflow

### 1. Fork & Clone

1. Fork the repository on GitHub: [https://github.com/PRAHULREDD/SCOS-App](https://github.com/PRAHULREDD/SCOS-App)
2. Clone your personal fork locally:

   ```bash
   git clone https://github.com/<your-username>/SCOS-App.git
   cd SCOS-App
   ```

3. Add the canonical repository as the `upstream` remote:

   ```bash
   git remote add upstream https://github.com/PRAHULREDD/SCOS-App.git
   ```

4. Create a topic branch with a descriptive name (example):

   ```bash
   git checkout -b fix-citizen-login
   ```

---

### 2. Environment Setup & Running Tests

Ensure you have Python 3.10 or later installed.

From the repository root:

```powershell
# Create and activate virtual environment
python -m venv backend/venv
.\backend\venv\Scripts\Activate.ps1
# (On Linux / macOS: source backend/venv/bin/activate)

# Install dependencies
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
```

#### Run the Automated Test Suite

Before making any changes, verify that the existing tests pass:

```powershell
python -m pytest backend/tests -o pythonpath=backend -q
```

*(Or from the `backend/` directory: `cd backend; pytest`)*

#### Run the Local Development Server

To run the FastAPI server locally:

```powershell
uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

Access the application in your browser at [http://127.0.0.1:8000/app/index.html](http://127.0.0.1:8000/app/index.html) or [http://127.0.0.1:8000/](http://127.0.0.1:8000/).

---

### 3. Implement Your Changes

- Keep modifications minimal and focused on the issue being addressed.
- Maintain existing coding conventions and asynchronous patterns (`SQLAlchemy 2.0 async`, `FastAPI`).
- Do not commit sensitive files, credentials, local `.env` files, or database binaries (`scos.db`).
- Add or update tests in `backend/tests/` to cover new logic or regressions.

---

### 4. Submitting a Pull Request

1. Fetch the latest changes from `upstream/main` and rebase your branch:

   ```bash
   git checkout main
   git fetch upstream
   git merge upstream/main
   git checkout fix-citizen-login
   git rebase main
   ```

2. Run the test suite and verify code hygiene:

   ```bash
   python -m pytest backend/tests -o pythonpath=backend -q
   flake8 backend --count --select=E9,F63,F7,F82 --show-source --statistics
   ```

3. Push your feature branch to your GitHub fork:

   ```bash
   git push -u origin fix-citizen-login
   ```

4. Open a Pull Request on GitHub against the `main` branch of `PRAHULREDD/SCOS-App`.
5. Provide a clear summary of your changes, referencing any relevant issue numbers.

---

## Keeping Your PR Updated

If new commits land on `main` before your PR is merged, update your branch:

```bash
git fetch upstream
git rebase upstream/main
git push --force-with-lease origin fix-citizen-login
```

Thank you for helping improve SCOS!
