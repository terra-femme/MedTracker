<!-- Copilot / Agent instructions for the MedTracker repo -->
# Brief

This file contains the minimal, repo-specific guidance an AI coding agent needs to be productive in MedTracker.

# Big picture (what this app is)
- **Type**: Single-repo FastAPI backend + static frontend (vanilla HTML/JS). See `main.py` and `frontend/index.html`.
- **Backend**: `main.py` (FastAPI app) mounts `frontend/` as static files and exposes REST endpoints under `/` and `/api/*`.
- **DB**: SQLite via SQLAlchemy. Engine and session factory live in `backend/database.py` and the DB file is `medtracker.db` in repo root.
- **Models & Schemas**: SQLAlchemy models in `backend/models.py`; Pydantic schemas in `backend/schemas.py` (Pydantic v2 style: `from_attributes = True`).
- **NLP**: Lightweight rule-based parser in `backend/med_nlp_parser.py`. The natural-language endpoint `/medications/natural` uses it.

# Quick dev workflows
- Create DB + sample data: `python setup_database.py` (runs from project root). This creates tables and optionally inserts sample rows.
- Run server (dev): `uvicorn main:app --reload` and open `http://localhost:8000`.
- Frontend expects API at `http://localhost:8000` (constant `API_BASE` in `frontend/index.html`).
- DB connection: `backend/database.py` uses `sqlite:///./medtracker.db` and `get_db()` yields Session for FastAPI `Depends`.

# Important code patterns & conventions
- Endpoints always acquire DB via `db: Session = Depends(get_db)` and use the pattern: create model, `db.add()`, `db.commit()`, `db.refresh()`.
  - Example in `main.py` (create medication): create `MedicationModel(...)`, `db.add(db_medication)`, `db.commit()`, `db.refresh(db_medication)`.
- Soft-delete convention: Deleting a medication sets `is_active = False` (see `DELETE /medications/{id}` in `main.py`). Do not remove rows unless explicitly changing cascade rules.
- Pydantic config: `backend/schemas.py` uses `from_attributes = True` for ORM compatibility (Pydantic v2). Alter carefully when upgrading Pydantic.
- Frequency strings are used as keys in both `med_nlp_parser.py` and `frontend/index.html` (e.g., `"Once daily"`, `"Twice daily"`, `"Every morning"`). Keep these aligned when changing frequency labels.
- NLP parser: `MedicationNLPParser` finds frequency, dosage, and name. Important details:
  - Frequency rules are matched longest-first to avoid partial matches. When modifying frequency patterns, maintain sorting-by-length behavior.
  - Dosage regex looks for numeric + unit (e.g., `500mg`, `2 tablets`). Update `dosage_units` in `med_nlp_parser.py` if adding new units.

# Integration points / external dependencies
- FastAPI + Uvicorn for server. See top-level `requirements.txt` for pinned packages.
- SQLite database file `medtracker.db` (created in repo root) — used directly by SQLAlchemy `create_engine` URL in `backend/database.py`.
- No external message queues or 3rd-party APIs are present; reminders are modelled in DB (`Reminder` table) but no scheduler is provided in repo.

# Where to look first when changing behavior
- Adding a new endpoint: follow patterns in `main.py`. Use `Depends(get_db)` and `schemas` response models.
- Changing database models: update `backend/models.py`, run `Base.metadata.create_all(bind=engine)` (or `python setup_database.py`) to create migrations-free tables. There is no Alembic here.
- Changing NLP: edit `backend/med_nlp_parser.py`. Run parser tests by invoking the file directly (`python backend/med_nlp_parser.py`) which runs `test_parser()`.
- Updating the UI mapping for frequency -> times: edit `frontend/index.html` `getTimesForFrequency()` to match backend frequency strings.

# Examples (copy-paste snippets you will see)
- Acquire DB session:
  `def my_route(db: Session = Depends(get_db)):`
- Create & save model:
  `db_med = MedicationModel(name=..., dosage=..., frequency=...); db.add(db_med); db.commit(); db.refresh(db_med)`

# Safety notes for agents
- Preserve the user-facing frequency strings; backend and frontend both rely on these exact strings.
- Do not remove `is_active` soft-delete behavior without updating UI and API semantics.
- The project uses SQLite + `StaticPool` in `backend/database.py`. Concurrency nuances exist (check_same_thread=False). For multi-process deployments, switch DB and update engine config.

# If unclear / missing
- If you need runtime context (installed packages, python version), ask the developer to run `pip freeze` inside the project venv and paste `requirements.txt`.
- For CI/test commands: none found — ask whether to add tests or CI workflows.

# Contact
- After making edits, ask the repo owner to run `uvicorn main:app --reload` and confirm that frontend (`index.html`) still renders and that `/medications` endpoints behave as expected.

-- End of guidance (ask for clarification to iterate)
