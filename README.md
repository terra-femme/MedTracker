# MedTracker

A medication safety AI system with a multi-agent pipeline for tracking schedules, checking drug interactions, and maintaining adherence records.

![MedTracker widget on iPhone showing 8am medication taken and 1pm pending](.github/images/medTracker_widget.jpeg)

## What it does

MedTracker combines a FastAPI backend with a LangGraph-orchestrated multi-agent system to handle medication management. Users track medications, receive reminders, and interact with an AI chatbot that checks drug interactions, calculates doses, and monitors adherence — with safety guardrails running on every input and response.

## AI Architecture

```
User Input
     │
     ▼
┌────────────────────────────────────────────────┐
│                 Safety Layer                   │
│   PIIDetector → ContentFilter → Emergency      │
└────────────────────────────────────────────────┘
     │
     ▼
┌────────────────────────────────────────────────┐
│         LangGraph V2 Orchestrator              │
│           (SQLite persistence)                 │
└───────────────┬────────────────────────────────┘
                │
     ┌──────────┴──────────────────────┐
     ▼                                 ▼
ClassifierAgent                   RAG Pipeline
     │                         Chroma + MMR retrieval
     ├── InteractionAgent       RxNorm API + OpenFDA API
     ├── DoseAgent
     ├── AdherenceAgent
     ├── ScheduleAgent
     ├── StreakAgent
     ├── MedicationAgent
     ├── GeneratorAgent
     ├── SafetyAgent
     └── AutocompleteAgent
```

## Safety Layer

Built from scratch — no third-party safety libraries.

- **PIIDetector**: Scans all inputs for 7 PHI pattern types (SSN, phone, email, MRN, DOB, credit card) with medical context scoring before any data is logged or persisted
- **MedicalContentFilter**: Blocks 10 categories of dangerous AI output including self-harm, prescription change suggestions, unqualified diagnoses, and emergency delay language
- **Emergency guardrail**: Detects overdose, crisis, and emergency keywords in real time; halts the pipeline and returns an immediate escalation response
- **HIPAA-aware design**: PHI is redacted before logging; SQLite audit trail persists conversation state across server restarts

## Technical Highlights

- **MMR retrieval for drug interaction diversity** — Chroma vector store uses maximal marginal relevance to balance relevance and diversity when retrieving drug interaction context from RxNorm and FDA label data
- **LangGraph V2 with SQLite persistence and message summarization** — conversation state survives server restarts; long sessions are summarized to stay within context limits while preserving safety warnings
- **Custom PIIDetector with 7 PHI pattern types and medical context scoring** — confidence score is boosted when medical context keywords are present alongside detected patterns, reducing false negatives in clinical language

## Stack

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI |
| AI orchestration | LangGraph V2, LangChain |
| Vector store | Chroma, HuggingFace embeddings |
| Drug data | RxNorm API, OpenFDA API |
| Database | SQLite |
| Frontend | HTML / CSS / JS |

## Running locally

```bash
git clone https://github.com/terra-femme/MedTracker.git
cd MedTracker
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python setup_database.py
python main.py
```

App runs at `http://localhost:8000`. Requires Python 3.9+.

## Tests

```bash
pytest tests/
```

## Author

Kristy (Terra Femme) — Healthcare IT engineer focused on multi-agent AI workflows and patient safety systems.
