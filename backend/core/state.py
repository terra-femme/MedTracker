"""
Shared application state — mutable singletons initialized at startup.

Routers import from here instead of using globals scattered across main.py.
"""
from backend.med_nlp_parser import MedicationNLPParser
from backend.medication_knowledge import MedicationKnowledgeBase

nlp_parser = MedicationNLPParser()
medication_kb = MedicationKnowledgeBase()

# Initialized dynamically by /chatbot/initialize and /chatbot/langgraph/initialize
rag_chatbot = None
langgraph_chatbot = None
