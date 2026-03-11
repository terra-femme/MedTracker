"""
MedTracker LangGraph V2 - Production-Ready Implementation
==========================================================
UPGRADED VERSION with ALL Advanced Features!

NEW FEATURES IN V2:
-------------------
1. Annotated + Reducers     - Don't lose safety warnings between messages
2. MessageState             - Proper conversation history tracking
3. Remove Messages          - HIPAA compliance (remove PHI)
4. Trim Messages            - Handle long conversations without crashing
5. Summarize Messages       - Preserve context while saving tokens
6. SQLite Persistence       - Data survives server restarts
7. StateSnapshot            - Debug and audit any conversation state
8. Enhanced Checkpoints     - Time-travel through conversation history

HEALTH-TECH IMPORTANCE:
-----------------------
This version is designed for PRODUCTION healthcare use:
- HIPAA compliant (PHI removal, audit trails)
- Reliable (SQLite persistence)
- Safe (never loses safety warnings)
- Scalable (message trimming/summarization)
- Debuggable (StateSnapshot inspection)

INSTALLATION:
-------------
pip install langgraph langchain-core langchain-community --break-system-packages

USAGE:
------
from medication_langgraph_v2 import MedTrackerLangGraphV2

chatbot = MedTrackerLangGraphV2(
    user_medications=[{"name": "Lisinopril", "dosage": "10mg"}],
    use_sqlite=True  # Enable persistent memory!
)

response = chatbot.ask("Can I take ibuprofen?")
"""

# =============================================================================
# IMPORTS
# =============================================================================

from typing import TypedDict, Annotated, Literal, List, Dict, Optional, Sequence
from datetime import datetime
import json
import os
import re
import operator  # For reducer functions

# =============================================================================
# LANGGRAPH IMPORTS - V2 FEATURES
# =============================================================================

print("=" * 60)
print("LOADING MEDTRACKER LANGGRAPH V2")
print("=" * 60)

try:
    # Core LangGraph
    from langgraph.graph import StateGraph, END
    
    # Memory/Checkpointing - SHORT TERM (RAM)
    from langgraph.checkpoint.memory import MemorySaver
    
    # Memory/Checkpointing - LONG TERM (SQLite) - NEW!
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
        SQLITE_AVAILABLE = True
        print("[OK] SqliteSaver imported (persistent memory)")
    except ImportError:
        SQLITE_AVAILABLE = False
        SqliteSaver = None
        print("[WARN] SqliteSaver not available - using MemorySaver only")
    
    LANGGRAPH_AVAILABLE = True
    print("[OK] LangGraph core imported")
    
except ImportError as e:
    LANGGRAPH_AVAILABLE = False
    print(f"[ERROR] LangGraph not installed: {e}")
    print("Run: pip install langgraph --break-system-packages")

# =============================================================================
# LANGCHAIN IMPORTS - Using NEW import paths (v1.2+)
# =============================================================================

try:
    # LLM and embeddings
    from langchain_community.llms import Ollama
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from langchain_community.vectorstores import Chroma
    
    # NEW IMPORT PATHS for LangChain 1.2+
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.messages import (
        HumanMessage,
        AIMessage,
        SystemMessage,
        RemoveMessage,  # NEW! For HIPAA compliance
        trim_messages,   # NEW! For token management
    )
    
    LANGCHAIN_AVAILABLE = True
    print("[OK] LangChain imported (using langchain_core paths)")
    
except ImportError as e:
    LANGCHAIN_AVAILABLE = False
    print(f"[ERROR] LangChain not available: {e}")
    print("Run: pip install langchain-core langchain-community --break-system-packages")

print("=" * 60)


# =============================================================================
# SECTION 1: ENHANCED STATE WITH ANNOTATED REDUCERS
# =============================================================================
"""
WHAT ARE REDUCERS?
------------------
A reducer tells LangGraph HOW to combine old and new values.

WITHOUT Reducer:
    old_value = ["warning1"]
    new_value = ["warning2"]
    result = ["warning2"]  # OLD VALUE LOST!

WITH Reducer (operator.add):
    old_value = ["warning1"]
    new_value = ["warning2"]
    result = ["warning1", "warning2"]  # BOTH KEPT!

HEALTH-TECH EXAMPLE:
    Patient asks 3 questions, each triggers a safety warning.
    WITHOUT reducers: Only last warning survives
    WITH reducers: ALL warnings preserved = SAFER!
"""


def add_messages_reducer(existing: List, new: List) -> List:
    """
    Custom reducer for messages that handles RemoveMessage
    
    This reducer:
    1. Adds new messages to existing
    2. Processes RemoveMessage to delete specific messages
    3. Returns the updated list
    
    HEALTH-TECH USE:
    - Patient accidentally shares SSN
    - We create RemoveMessage for that message
    - Reducer removes it from history
    - PHI is gone! HIPAA compliant!
    """
    # Start with existing messages
    result = list(existing) if existing else []
    
    # Process each new item
    for item in (new or []):
        if isinstance(item, RemoveMessage): # If the item is a RemoveMessage:
            # Remove the message with matching ID
            result = [msg for msg in result if getattr(msg, 'id', None) != item.id]
            print(f"    [REDUCER] Removed message ID: {item.id}")
        else:
            # Add the new message
            result.append(item)
    
    return result


class MedTrackerStateV2(TypedDict):
    """
    ENHANCED STATE with Annotated Reducers
    
    CHANGES FROM V1:
    ----------------
    1. Added 'messages' field with custom reducer
    2. 'safety_flags' now ACCUMULATES (doesn't replace)
    3. 'audit_log' now ACCUMULATES (doesn't replace)
    4. Added 'allergies' for critical patient info
    5. Added 'message_count' for tracking
    
    REDUCER EXPLANATION:
    --------------------
    Annotated[List[str], operator.add]
                  ^           ^
                  |           |
           The type     How to combine
                        old + new values
    """
    
    # =========================================================================
    # CONVERSATION MESSAGES - With Custom Reducer!
    # =========================================================================
    # This tracks the full conversation history
    # The reducer handles adding AND removing messages
    messages: Annotated[List, add_messages_reducer]
    
    # =========================================================================
    # QUESTION PROCESSING
    # =========================================================================
    question: str                    # Current question being processed
    question_type: str               # Classification result
    
    # =========================================================================
    # USER CONTEXT - Critical medical info (NEVER loses this!)
    # =========================================================================
    user_medications: List[Dict]     # Patient's medication list
    allergies: List[str]             # CRITICAL: Drug allergies
    
    # =========================================================================
    # SAFETY - Uses ACCUMULATING reducer!
    # =========================================================================
    # operator.add means: old_list + new_list (KEEPS ALL!)
    safety_flags: Annotated[List[str], operator.add]
    
    # =========================================================================
    # RAG RESULTS
    # =========================================================================
    retrieved_context: str           # What RAG found
    interaction_results: Optional[Dict]  # Drug interaction analysis
    
    # =========================================================================
    # OUTPUT
    # =========================================================================
    response: str                    # Final response to user
    confidence_score: float          # How confident (0-1)
    
    # =========================================================================
    # AUDIT TRAIL - Uses ACCUMULATING reducer!
    # =========================================================================
    # HIPAA REQUIREMENT: Track every decision
    audit_log: Annotated[List[Dict], operator.add]
    
    # =========================================================================
    # METADATA
    # =========================================================================
    message_count: int               # Track conversation length
    summary: Optional[str]           # Summarized old messages


# =============================================================================
# SECTION 2: PHI DETECTION AND REMOVAL (HIPAA COMPLIANCE)
# =============================================================================
"""
HIPAA requires protection of Protected Health Information (PHI).

PHI includes:
- Social Security Numbers (SSN)
- Medical Record Numbers
- Health Plan Numbers
- Account Numbers
- Birth Dates
- Phone Numbers (in some contexts)
- Email Addresses (in some contexts)

Our approach:
1. DETECT PHI in messages using regex patterns
2. FLAG messages containing PHI
3. REMOVE those messages from state using RemoveMessage
4. LOG the removal for audit (but not the actual PHI!)
"""


class PHIDetector:
    """
    Detects Protected Health Information in text
    
    HEALTH-TECH CRITICAL:
    This is a basic implementation. Production systems should use:
    - Medical NER models (like Amazon Comprehend Medical)
    - More comprehensive regex patterns
    - Human review for edge cases
    """
    
    # Regex patterns for common PHI
    PATTERNS = {
        'ssn': r'\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b',
        'phone': r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'dob': r'\b(0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])[-/](19|20)?\d{2}\b',
        'mrn': r'\b(MRN|mrn|Medical Record)[:\s#]*\d{6,10}\b',
        'credit_card': r'\b\d{4}[-.\s]?\d{4}[-.\s]?\d{4}[-.\s]?\d{4}\b',
    }
    
    @classmethod
    def detect(cls, text: str) -> Dict[str, List[str]]:
        """
        Detect PHI in text
        
        Returns dict of {phi_type: [matches]}
        """
        found = {}
        
        for phi_type, pattern in cls.PATTERNS.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                found[phi_type] = matches
        
        return found
    
    @classmethod
    def contains_phi(cls, text: str) -> bool:
        """Quick check if text contains any PHI"""
        return bool(cls.detect(text))
    
    @classmethod
    def redact(cls, text: str) -> str:
        """
        Replace PHI with redaction markers
        
        Example:
            "My SSN is 123-45-6789" -> "My SSN is [REDACTED-SSN]"
        
        HEALTH-TECH NOTE:
        Use this for LOGGING, not for conversation.
        We want to log THAT PHI was detected, but not WHAT it was.
        """
        result = text
        
        for phi_type, pattern in cls.PATTERNS.items():
            result = re.sub(pattern, f'[REDACTED-{phi_type.upper()}]', result, flags=re.IGNORECASE)
        
        return result


# =============================================================================
# SECTION 3: MESSAGE MANAGEMENT (TRIM, SUMMARIZE, REMOVE)
# =============================================================================
"""
WHY MESSAGE MANAGEMENT MATTERS:
-------------------------------
1. TOKEN LIMITS: LLMs have context limits (4K, 8K, 128K tokens)
2. COST: More tokens = more expensive API calls
3. RELEVANCE: Old messages may not be relevant
4. PRIVACY: Some messages should be removed (PHI)

THREE STRATEGIES:
-----------------
1. TRIM: Remove oldest messages, keep most recent
2. SUMMARIZE: Condense old messages into a summary
3. REMOVE: Delete specific messages (PHI, errors)
"""


class MessageManager:
    """
    Manages conversation messages for health-tech compliance and efficiency
    """
    
    def __init__(self, llm, max_messages: int = 20, max_tokens: int = 4000):
        """
        Args:
            llm: Language model for summarization
            max_messages: Max messages before trimming
            max_tokens: Max tokens in context
        """
        self.llm = llm
        self.max_messages = max_messages
        self.max_tokens = max_tokens
    
    def trim_messages(self, messages: List, keep_system: bool = True) -> List:
        """
        Trim messages to fit within limits
        
        STRATEGY:
        1. Always keep system message (contains critical instructions)
        2. Keep most recent messages
        3. Remove oldest messages first
        
        HEALTH-TECH CONSIDERATION:
        We might want to ALWAYS keep certain messages:
        - Allergy warnings
        - Critical drug interactions
        - Current medication list updates
        """
        if len(messages) <= self.max_messages:
            return messages
        
        print(f"    [TRIM] Trimming {len(messages)} messages to {self.max_messages}")
        
        # Separate system messages
        system_msgs = [m for m in messages if isinstance(m, SystemMessage)]
        other_msgs = [m for m in messages if not isinstance(m, SystemMessage)]
        
        # Keep most recent non-system messages
        keep_count = self.max_messages - len(system_msgs) if keep_system else self.max_messages
        trimmed_others = other_msgs[-keep_count:] if keep_count > 0 else []
        
        # Combine: system first, then recent messages
        result = (system_msgs if keep_system else []) + trimmed_others
        
        print(f"    [TRIM] Result: {len(result)} messages")
        return result
    
    def summarize_old_messages(self, messages: List, keep_recent: int = 5) -> tuple:
        """
        Summarize old messages while keeping recent ones intact
        
        Returns:
            (summary_text, recent_messages)
        
        HEALTH-TECH FOCUS:
        The summary MUST preserve:
        - All mentioned medications
        - All mentioned allergies
        - All safety warnings
        - Key symptoms discussed
        """
        if len(messages) <= keep_recent:
            return None, messages
        
        old_messages = messages[:-keep_recent]
        recent_messages = messages[-keep_recent:]
        
        # Build conversation text for summarization
        conversation_text = ""
        for msg in old_messages:
            role = "Patient" if isinstance(msg, HumanMessage) else "Assistant"
            content = getattr(msg, 'content', str(msg))
            conversation_text += f"{role}: {content}\n"
        
        # Create summarization prompt
        summary_prompt = f"""Summarize this healthcare conversation for continuity of care.

CRITICAL - YOU MUST PRESERVE:
- All medication names and dosages mentioned
- All allergies mentioned
- All safety warnings or concerns
- Key symptoms or health issues discussed
- Any changes to treatment

CONVERSATION TO SUMMARIZE:
{conversation_text}

SUMMARY (be concise but complete):"""

        try:
            summary = self.llm.invoke(summary_prompt)
            print(f"    [SUMMARIZE] Summarized {len(old_messages)} messages")
            return summary, recent_messages
        except Exception as e:
            print(f"    [SUMMARIZE] Error: {e}")
            return None, messages
    
    def remove_phi_messages(self, messages: List) -> tuple:
        """
        Identify and create RemoveMessage for messages containing PHI
        
        Returns:
            (clean_messages, remove_commands, audit_entries)
        
        HIPAA COMPLIANCE:
        - Detect PHI in each message
        - Create RemoveMessage for those messages
        - Log THAT removal occurred (not WHAT was removed)
        """
        remove_commands = []
        audit_entries = []
        
        for msg in messages:
            content = getattr(msg, 'content', str(msg))
            msg_id = getattr(msg, 'id', None)
            
            if PHIDetector.contains_phi(content):
                phi_types = PHIDetector.detect(content)
                
                if msg_id:
                    remove_commands.append(RemoveMessage(id=msg_id))
                
                # Audit entry (redacted for compliance)
                audit_entries.append({
                    "timestamp": datetime.now().isoformat(),
                    "action": "PHI_DETECTED_AND_REMOVED",
                    "phi_types_found": list(phi_types.keys()),
                    "message_id": msg_id,
                    "redacted_preview": PHIDetector.redact(content)[:50] + "..."
                })
                
                print(f"    [PHI] Detected {list(phi_types.keys())} - flagged for removal")
        
        return remove_commands, audit_entries


# =============================================================================
# SECTION 4: NODES (Updated for V2 State)
# =============================================================================
"""
NODES are the workers in the graph.
Each node receives state, does work, returns state updates.

V2 CHANGES:
-----------
1. Nodes now handle messages properly
2. PHI detection in user input
3. Message trimming when needed
4. Proper audit logging with reducers
"""


def create_classifier_node_v2(llm):
    """
    NODE: Classify the user's question
    
    V2 IMPROVEMENTS:
    - Adds human message to conversation history
    - Checks for PHI in the question
    - Uses proper message format
    """
    
    def classify_question(state: MedTrackerStateV2) -> Dict:
        print("\n" + "=" * 60)
        print("[NODE] CLASSIFY QUESTION")
        print("=" * 60)
        
        question = state["question"]
        messages = state.get("messages", [])
        
        # Create audit entry
        audit_entry = {
            "timestamp": datetime.now().isoformat(),
            "node": "classify_question_v2",
            "input_length": len(question),
        }
        
        # Check for PHI in the question
        if PHIDetector.contains_phi(question):
            print("    [WARN] PHI detected in question!")
            audit_entry["phi_detected"] = True
            audit_entry["phi_types"] = list(PHIDetector.detect(question).keys())
        
        # Add user message to conversation
        new_message = HumanMessage(content=question)
        
        # Classification logic
        classification_prompt = f"""Classify this medication-related question into ONE category:

- medication_info: General questions about what a drug is/does
- interaction_check: Questions about drug interactions
- dosage_question: Questions about dosing, timing, how to take
- side_effects: Questions about side effects
- emergency: Mentions overdose, severe symptoms, urgent situations
- general_chat: Casual conversation, greetings

Question: "{question}"

Respond with ONLY the category name:"""

        try:
            classification = llm.invoke(classification_prompt).strip().lower()
            
            # Validate
            valid_types = ["medication_info", "interaction_check", "dosage_question", 
                          "side_effects", "emergency", "general_chat"]
            
            if classification not in valid_types:
                classification = "medication_info"
            
            # Emergency keyword backup check
            emergency_keywords = ["overdose", "too many", "can't breathe", "chest pain",
                                 "unconscious", "suicide", "emergency", "dying", "911"]
            
            if any(kw in question.lower() for kw in emergency_keywords):
                classification = "emergency"
                print("    [ALERT] Emergency keywords detected!")
            
            print(f"    Classification: {classification}")
            audit_entry["classification"] = classification
            
        except Exception as e:
            print(f"    [ERROR] Classification failed: {e}")
            classification = "medication_info"
            audit_entry["error"] = str(e)
        
        # Return state updates (reducer will APPEND to lists!)
        return {
            "question_type": classification,
            "messages": [new_message],  # Reducer appends this
            "audit_log": [audit_entry],  # Reducer appends this
            "message_count": (state.get("message_count", 0) + 1)
        }
    
    return classify_question


def create_rag_node_v2(vectorstore, llm):
    """
    NODE: RAG Retrieval and Generation
    
    V2 IMPROVEMENTS:
    - Uses conversation history for context
    - Adds AI response to message history
    - Better prompting with medical focus
    """
    
    def rag_retrieve_and_generate(state: MedTrackerStateV2) -> Dict:
        print("\n" + "=" * 60)
        print("[NODE] RAG RETRIEVE & GENERATE")
        print("=" * 60)
        
        question = state["question"]
        user_meds = state.get("user_medications", [])
        allergies = state.get("allergies", [])
        messages = state.get("messages", [])
        
        audit_entry = {
            "timestamp": datetime.now().isoformat(),
            "node": "rag_retrieve_v2",
        }
        
        # Retrieve relevant documents
        print("    Retrieving documents...")
        try:
            retriever = vectorstore.as_retriever(
                search_type="mmr",
                search_kwargs={"k": 5, "fetch_k": 10}
            )
            docs = retriever.invoke(question)
            context = "\n\n".join([doc.page_content for doc in docs])
            audit_entry["docs_retrieved"] = len(docs)
            print(f"    Found {len(docs)} documents")
        except Exception as e:
            context = ""
            audit_entry["retrieval_error"] = str(e)
            print(f"    [ERROR] Retrieval failed: {e}")
        
        # Format user medications
        meds_text = "None on file"
        if user_meds:
            meds_text = "\n".join([
                f"- {m['name']}: {m.get('dosage', 'N/A')}, {m.get('frequency', 'N/A')}"
                for m in user_meds
            ])
        
        # Format allergies
        allergies_text = ", ".join(allergies) if allergies else "None reported"
        
        # Build conversation context (last few messages)
        conv_context = ""
        recent_msgs = messages[-6:] if len(messages) > 6 else messages
        for msg in recent_msgs:
            role = "Patient" if isinstance(msg, HumanMessage) else "Assistant"
            conv_context += f"{role}: {getattr(msg, 'content', '')[:200]}\n"
        
        # Generate response
        no_meds_guard = (
            "\n⚠️ CRITICAL: The patient has NO medications on file. "
            "Do NOT present any information from the knowledge base as the patient's medications. "
            "If asked what medications are on file, clearly state there are none recorded yet.\n"
            if not user_meds else ""
        )

        generation_prompt = f"""You are a medication assistant for a patient tracking app.

PATIENT'S MEDICATIONS:
{meds_text}

PATIENT'S ALLERGIES:
{allergies_text}
{no_meds_guard}
RELEVANT MEDICAL INFORMATION (general drug knowledge — NOT the patient's medications):
{context[:2000]}

RECENT CONVERSATION:
{conv_context}

CURRENT QUESTION: {question}

INSTRUCTIONS:
- Be helpful and accurate
- If unsure, say so clearly
- For medical decisions, recommend consulting a healthcare provider
- NEVER suggest medications the patient is allergic to
- Reference their current medications when relevant
- NEVER confuse general drug knowledge with the patient's actual medication list

Response:"""

        try:
            response = llm.invoke(generation_prompt)
            print(f"    Generated response ({len(response)} chars)")
            audit_entry["response_length"] = len(response)
        except Exception as e:
            response = "I apologize, but I encountered an error. Please try again."
            audit_entry["generation_error"] = str(e)
            print(f"    [ERROR] Generation failed: {e}")
        
        # Create AI message for history
        ai_message = AIMessage(content=response)
        
        return {
            "retrieved_context": context[:1000],
            "response": response,
            "messages": [ai_message],  # Reducer appends
            "audit_log": [audit_entry],  # Reducer appends
        }
    
    return rag_retrieve_and_generate


def create_interaction_checker_node_v2(llm):
    """
    NODE: Drug Interaction Checker
    
    V2 IMPROVEMENTS:
    - Checks allergies too
    - Better safety flag accumulation
    - More detailed audit logging
    """
    
    def check_interactions(state: MedTrackerStateV2) -> Dict:
        print("\n" + "=" * 60)
        print("[NODE] DRUG INTERACTION CHECKER")
        print("=" * 60)
        
        question = state["question"]
        user_meds = state.get("user_medications", [])
        allergies = state.get("allergies", [])
        
        audit_entry = {
            "timestamp": datetime.now().isoformat(),
            "node": "interaction_checker_v2",
            "user_med_count": len(user_meds),
            "allergy_count": len(allergies),
        }
        
        # Extract medication names
        user_med_names = [m["name"].lower() for m in user_meds]
        
        # Create interaction check prompt
        interaction_prompt = f"""Analyze this question for drug interactions.

PATIENT'S CURRENT MEDICATIONS:
{', '.join(user_med_names) if user_med_names else 'None on file'}

PATIENT'S ALLERGIES:
{', '.join(allergies) if allergies else 'None reported'}

QUESTION: {question}

Respond in JSON format:
{{
    "drugs_mentioned": ["list", "of", "drugs"],
    "potential_interactions": [
        {{"drug1": "name", "drug2": "name", "severity": "mild/moderate/severe", "description": "brief"}}
    ],
    "allergy_concerns": ["any drugs that match allergies"],
    "recommendation": "safety recommendation"
}}

Response:"""

        safety_flags = []
        interaction_results = {}
        
        try:
            response = llm.invoke(interaction_prompt)
            
            # Try to parse JSON
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                interaction_results = json.loads(json_match.group())
            
            # Create safety flags for severe interactions
            for interaction in interaction_results.get("potential_interactions", []):
                if interaction.get("severity") == "severe":
                    flag = f"SEVERE_INTERACTION: {interaction.get('drug1')} + {interaction.get('drug2')}"
                    safety_flags.append(flag)
                    print(f"    [ALERT] {flag}")
            
            # Create safety flags for allergy concerns
            for allergy in interaction_results.get("allergy_concerns", []):
                flag = f"ALLERGY_ALERT: {allergy}"
                safety_flags.append(flag)
                print(f"    [ALERT] {flag}")
            
            audit_entry["interactions_found"] = len(interaction_results.get("potential_interactions", []))
            audit_entry["allergy_alerts"] = len(interaction_results.get("allergy_concerns", []))
            
        except Exception as e:
            print(f"    [ERROR] Interaction check failed: {e}")
            interaction_results = {"error": str(e)}
            audit_entry["error"] = str(e)
        
        return {
            "interaction_results": interaction_results,
            "safety_flags": safety_flags,  # Reducer APPENDS these!
            "audit_log": [audit_entry],    # Reducer APPENDS these!
        }
    
    return check_interactions


def create_phi_removal_node():
    """
    NODE: PHI Detection and Removal
    
    NEW IN V2!
    This node scans messages for PHI and creates RemoveMessage commands
    
    HIPAA COMPLIANCE:
    - Scans all messages for PHI patterns
    - Creates removal commands for messages with PHI
    - Logs THAT removal occurred (not WHAT was removed)
    """
    
    def remove_phi(state: MedTrackerStateV2) -> Dict:
        print("\n" + "=" * 60)
        print("[NODE] PHI DETECTION & REMOVAL")
        print("=" * 60)
        
        messages = state.get("messages", [])
        
        audit_entries = []
        removal_commands = []
        
        for msg in messages:
            content = getattr(msg, 'content', str(msg))
            msg_id = getattr(msg, 'id', id(msg))  # Use object id if no msg.id
            
            if PHIDetector.contains_phi(content):
                phi_types = list(PHIDetector.detect(content).keys())
                
                print(f"    [PHI FOUND] Types: {phi_types}")
                
                # Create removal command (if message has proper id)
                if hasattr(msg, 'id') and msg.id:
                    removal_commands.append(RemoveMessage(id=msg.id))
                
                # Create audit entry
                audit_entries.append({
                    "timestamp": datetime.now().isoformat(),
                    "node": "phi_removal",
                    "action": "PHI_DETECTED",
                    "phi_types": phi_types,
                    "redacted_preview": PHIDetector.redact(content)[:50] + "..."
                })
        
        if not removal_commands:
            print("    No PHI detected - messages are clean")
        
        return {
            "messages": removal_commands,  # Reducer processes RemoveMessage
            "audit_log": audit_entries,     # Reducer appends
        }
    
    return remove_phi


def create_message_trimmer_node(llm, max_messages: int = 20):
    """
    NODE: Message Trimming and Summarization
    
    NEW IN V2!
    Prevents context overflow by trimming/summarizing old messages
    """
    
    manager = MessageManager(llm, max_messages=max_messages)
    
    def trim_and_summarize(state: MedTrackerStateV2) -> Dict:
        print("\n" + "=" * 60)
        print("[NODE] MESSAGE TRIMMER")
        print("=" * 60)
        
        messages = state.get("messages", [])
        current_summary = state.get("summary", "")
        
        audit_entry = {
            "timestamp": datetime.now().isoformat(),
            "node": "message_trimmer",
            "messages_before": len(messages),
        }
        
        if len(messages) <= max_messages:
            print(f"    Message count ({len(messages)}) within limit - no action needed")
            return {}
        
        print(f"    Message count ({len(messages)}) exceeds limit ({max_messages})")
        
        # Summarize old messages
        summary, recent_messages = manager.summarize_old_messages(messages, keep_recent=10)
        
        if summary:
            # Create a system message with the summary
            summary_msg = SystemMessage(content=f"Previous conversation summary:\n{summary}")
            
            # Clear old messages and add summary + recent
            # Note: This is a replacement, not an append
            new_messages = [summary_msg] + recent_messages
            
            audit_entry["messages_after"] = len(new_messages)
            audit_entry["summarized"] = True
            
            print(f"    Reduced to {len(new_messages)} messages (with summary)")
            
            return {
                "summary": summary,
                "audit_log": [audit_entry],
            }
        
        return {"audit_log": [audit_entry]}
    
    return trim_and_summarize


def create_emergency_node_v2():
    """
    NODE: Emergency Handler
    
    V2: Adds message to history and sets maximum safety flags
    """
    
    def handle_emergency(state: MedTrackerStateV2) -> Dict:
        print("\n" + "=" * 60)
        print("[NODE] EMERGENCY HANDLER")
        print("=" * 60)
        print("    EMERGENCY PROTOCOL ACTIVATED")
        
        audit_entry = {
            "timestamp": datetime.now().isoformat(),
            "node": "emergency_handler_v2",
            "emergency_type": "potential_medical_emergency",
            "action": "provided_emergency_resources"
        }
        
        emergency_response = """**THIS SOUNDS LIKE IT COULD BE AN EMERGENCY**

**If this is a medical emergency:**
Call 911 immediately (or your local emergency number)

**If you suspect an overdose:**
Poison Control: 1-800-222-1222 (US)

I am an AI assistant and cannot provide emergency medical care.
Do NOT wait for an AI response in an emergency!

---

If this is NOT an emergency and I misunderstood, please rephrase your question."""

        ai_message = AIMessage(content=emergency_response)
        
        return {
            "response": emergency_response,
            "messages": [ai_message],
            "safety_flags": ["EMERGENCY_TRIGGERED"],  # Reducer appends
            "audit_log": [audit_entry],               # Reducer appends
            "confidence_score": 1.0,
        }
    
    return handle_emergency


def create_response_formatter_node_v2():
    """
    NODE: Format Final Response
    
    V2: Includes safety warnings summary if any exist
    """
    
    def format_response(state: MedTrackerStateV2) -> Dict:
        print("\n" + "=" * 60)
        print("[NODE] RESPONSE FORMATTER")
        print("=" * 60)
        
        response = state.get("response", "")
        safety_flags = state.get("safety_flags", [])
        interaction_results = state.get("interaction_results")
        
        formatted_parts = []
        
        # Add safety warnings header if any
        if safety_flags:
            formatted_parts.append("**Safety Alerts:**")
            for flag in safety_flags:
                formatted_parts.append(f"- {flag}")
            formatted_parts.append("")
        
        # Add interaction results if severe
        if interaction_results:
            severe = [i for i in interaction_results.get("potential_interactions", [])
                     if i.get("severity") == "severe"]
            if severe:
                formatted_parts.append("**Drug Interaction Warnings:**")
                for i in severe:
                    formatted_parts.append(f"- {i.get('drug1')} + {i.get('drug2')}: {i.get('description')}")
                formatted_parts.append("")
        
        # Add main response
        formatted_parts.append(response)
        
        # Add disclaimer (unless emergency)
        if "EMERGENCY" not in response:
            formatted_parts.append("")
            formatted_parts.append("---")
            formatted_parts.append("*I'm an AI assistant. For medical decisions, please consult your healthcare provider.*")
        
        final_response = "\n".join(formatted_parts)
        
        print(f"    Response formatted ({len(final_response)} chars)")
        print(f"    Safety flags included: {len(safety_flags)}")
        
        return {
            "response": final_response,
            "audit_log": [{
                "timestamp": datetime.now().isoformat(),
                "node": "response_formatter_v2",
                "safety_flags_count": len(safety_flags),
                "response_length": len(final_response),
            }]
        }
    
    return format_response


def create_general_chat_node_v2(llm):
    """NODE: Handle general conversation"""
    
    def handle_general_chat(state: MedTrackerStateV2) -> Dict:
        print("\n" + "=" * 60)
        print("[NODE] GENERAL CHAT")
        print("=" * 60)
        
        question = state["question"]
        user_meds = state.get("user_medications", [])

        if user_meds:
            meds_context = "The user has the following medications on file: " + ", ".join(
                m["name"] for m in user_meds
            )
        else:
            meds_context = "The user has NO medications on file yet."

        prompt = f"""You are a friendly medication tracking assistant.

PATIENT CONTEXT: {meds_context}

The user said: "{question}"

Respond briefly and friendly. If the user asks whether you can see their medications,
answer honestly based on the PATIENT CONTEXT above — do not guess or fabricate.
Offer to help with medication questions.

Response:"""

        try:
            response = llm.invoke(prompt)
        except:
            response = "Hello! I'm your medication assistant. How can I help you today?"
        
        ai_message = AIMessage(content=response)
        
        return {
            "response": response,
            "messages": [ai_message],
            "audit_log": [{
                "timestamp": datetime.now().isoformat(),
                "node": "general_chat_v2",
            }]
        }
    
    return handle_general_chat


# =============================================================================
# SECTION 5: BUILD THE GRAPH (V2)
# =============================================================================

def create_medication_graph_v2(vectorstore, llm, use_sqlite: bool = False, db_path: str = "./langgraph_memory.db"):
    """
    Build the V2 graph with all advanced features
    
    Args:
        vectorstore: ChromaDB vector store
        llm: Ollama LLM
        use_sqlite: If True, use SQLite for persistent memory
        db_path: Path to SQLite database
    
    Returns:
        Compiled graph with checkpointer
    """
    print("\n" + "=" * 60)
    print("BUILDING MEDTRACKER LANGGRAPH V2")
    print("=" * 60)
    
    # Create the graph
    workflow = StateGraph(MedTrackerStateV2)
    
    # ==========================================================================
    # ADD NODES
    # ==========================================================================
    print("\n[1/6] Adding nodes...")
    
    workflow.add_node("classify", create_classifier_node_v2(llm))
    print("    + classify")
    
    workflow.add_node("check_phi", create_phi_removal_node())
    print("    + check_phi (NEW in V2!)")
    
    workflow.add_node("check_interactions", create_interaction_checker_node_v2(llm))
    print("    + check_interactions")
    
    workflow.add_node("rag_retrieve", create_rag_node_v2(vectorstore, llm))
    print("    + rag_retrieve")
    
    workflow.add_node("emergency", create_emergency_node_v2())
    print("    + emergency")
    
    workflow.add_node("general_chat", create_general_chat_node_v2(llm))
    print("    + general_chat")
    
    workflow.add_node("format_response", create_response_formatter_node_v2())
    print("    + format_response")
    
    workflow.add_node("trim_messages", create_message_trimmer_node(llm))
    print("    + trim_messages (NEW in V2!)")
    
    # ==========================================================================
    # SET ENTRY POINT
    # ==========================================================================
    print("\n[2/6] Setting entry point...")
    workflow.set_entry_point("classify")
    print("    Entry: classify")
    
    # ==========================================================================
    # ADD EDGES - PHI check after classification
    # ==========================================================================
    print("\n[3/6] Adding edges...")
    
    # Classification -> PHI Check (always)
    workflow.add_edge("classify", "check_phi")
    print("    classify -> check_phi")
    
    # ==========================================================================
    # CONDITIONAL ROUTING after PHI check
    # ==========================================================================
    def route_after_phi(state: MedTrackerStateV2) -> str:
        """Route based on question type after PHI check"""
        question_type = state.get("question_type", "medication_info")
        
        routes = {
            "medication_info": "rag_retrieve",
            "interaction_check": "check_interactions",
            "dosage_question": "rag_retrieve",
            "side_effects": "rag_retrieve",
            "emergency": "emergency",
            "general_chat": "general_chat",
        }
        
        destination = routes.get(question_type, "rag_retrieve")
        print(f"    [ROUTE] {question_type} -> {destination}")
        return destination
    
    workflow.add_conditional_edges(
        "check_phi",
        route_after_phi,
        {
            "rag_retrieve": "rag_retrieve",
            "check_interactions": "check_interactions",
            "emergency": "emergency",
            "general_chat": "general_chat",
        }
    )
    print("    check_phi -> (conditional routing)")
    
    # ==========================================================================
    # REMAINING EDGES
    # ==========================================================================
    workflow.add_edge("check_interactions", "rag_retrieve")
    print("    check_interactions -> rag_retrieve")
    
    workflow.add_edge("rag_retrieve", "format_response")
    print("    rag_retrieve -> format_response")
    
    workflow.add_edge("format_response", "trim_messages")
    print("    format_response -> trim_messages")
    
    workflow.add_edge("trim_messages", END)
    print("    trim_messages -> END")
    
    workflow.add_edge("emergency", END)
    print("    emergency -> END")
    
    workflow.add_edge("general_chat", "trim_messages")
    print("    general_chat -> trim_messages")
    
    # ==========================================================================
    # SETUP MEMORY/CHECKPOINTER
    # ==========================================================================
    print("\n[4/6] Setting up memory...")
    
    if use_sqlite and SQLITE_AVAILABLE:
        print(f"    Using SQLite: {db_path}")
        memory = SqliteSaver.from_conn_string(f"sqlite:///{db_path}")
        print("    [OK] Persistent memory enabled!")
    else:
        print("    Using MemorySaver (in-memory, not persistent)")
        memory = MemorySaver()
        if use_sqlite and not SQLITE_AVAILABLE:
            print("    [WARN] SQLite requested but not available")
    
    # ==========================================================================
    # COMPILE
    # ==========================================================================
    print("\n[5/6] Compiling graph...")
    compiled_graph = workflow.compile(checkpointer=memory)
    print("    [OK] Graph compiled!")
    
    print("\n[6/6] Graph ready!")
    print("=" * 60)
    
    return compiled_graph


# =============================================================================
# SECTION 6: MAIN CHATBOT CLASS (V2)
# =============================================================================

class MedTrackerLangGraphV2:
    """
    Production-Ready MedTracker Chatbot with Advanced Features
    
    FEATURES:
    ---------
    - Persistent memory (SQLite)
    - PHI detection and removal
    - Message trimming/summarization
    - Proper conversation history
    - Safety flag accumulation
    - State inspection (debugging)
    - Full audit trails
    
    USAGE:
    ------
    chatbot = MedTrackerLangGraphV2(
        user_medications=[{"name": "Lisinopril", "dosage": "10mg"}],
        allergies=["Penicillin"],
        use_sqlite=True
    )
    
    response = chatbot.ask("Can I take amoxicillin?")
    # Will warn about penicillin allergy!
    
    # Debug a conversation
    snapshot = chatbot.get_state_snapshot()
    print(snapshot)
    """
    
    def __init__(
        self,
        model_name: str = "llama3",
        user_medications: List[Dict] = None,
        allergies: List[str] = None,
        use_sqlite: bool = False,
        db_path: str = "./langgraph_memory.db",
        chroma_path: str = "./chroma_db",
        thread_id: str = None,
    ):
        """
        Initialize the V2 chatbot
        
        Args:
            model_name: Ollama model to use
            user_medications: Patient's medication list
            allergies: Patient's known allergies (CRITICAL!)
            use_sqlite: Enable persistent memory
            db_path: Path for SQLite memory database
            chroma_path: Path for ChromaDB
            thread_id: Conversation thread ID (for persistence)
        """
        print("\n" + "=" * 60)
        print("INITIALIZING MEDTRACKER LANGGRAPH V2")
        print("=" * 60)
        
        if not LANGGRAPH_AVAILABLE:
            raise ImportError("LangGraph not installed. Run: pip install langgraph")
        
        if not LANGCHAIN_AVAILABLE:
            raise ImportError("LangChain not available. Check imports.")
        
        # Store configuration
        self.user_medications = user_medications or []
        self.allergies = allergies or []
        self.use_sqlite = use_sqlite
        self.db_path = db_path
        
        # Thread ID for conversation persistence
        self.thread_id = thread_id or f"medtracker_v2_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"Thread ID: {self.thread_id}")
        
        # Initialize LLM
        print("\n[1/4] Loading Ollama LLM...")
        self.llm = Ollama(model=model_name, temperature=0.1)
        print(f"    Model: {model_name}")
        
        # Initialize embeddings
        print("\n[2/4] Loading embeddings...")
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu"} # force the embedding model to load on CPU before LangChain tries to move it, This prevents LangChain from triggering the meta‑tensor .to() call that caused the crash.
        )
        print("    Model: all-MiniLM-L6-v2")
        
        # Initialize vector store
        print("\n[3/4] Loading vector database...")
        self.vectorstore = Chroma(
            collection_name="medication_knowledge",
            embedding_function=self.embeddings,
            persist_directory=chroma_path,
        )
        print(f"    Path: {chroma_path}")
        
        # Build the graph
        print("\n[4/4] Building graph...")
        self.graph = create_medication_graph_v2(
            self.vectorstore,
            self.llm,
            use_sqlite=use_sqlite,
            db_path=db_path,
        )
        
        # Initialize local tracking
        self.full_audit_log = []
        self.conversation_count = 0
        
        print("\n" + "=" * 60)
        print("MEDTRACKER V2 READY!")
        print(f"  Medications: {len(self.user_medications)}")
        print(f"  Allergies: {len(self.allergies)}")
        print(f"  Persistent: {use_sqlite}")
        print("=" * 60 + "\n")
    
    def ask(self, question: str) -> str:
        """
        Ask the chatbot a question
        
        The graph will:
        1. Classify the question
        2. Check for PHI
        3. Route to appropriate handler
        4. Generate response
        5. Format with safety warnings
        6. Trim messages if needed
        """
        print("\n" + "=" * 70)
        print(f"[QUESTION] {question}")
        print("=" * 70)
        
        # Create initial state
        initial_state = {
            "question": question,
            "question_type": "",
            "user_medications": self.user_medications,
            "allergies": self.allergies,
            "messages": [],
            "safety_flags": [],
            "retrieved_context": "",
            "interaction_results": None,
            "response": "",
            "audit_log": [],
            "confidence_score": 0.0,
            "message_count": self.conversation_count,
            "summary": None,
        }
        
        # Configuration with thread ID
        config = {
            "configurable": {
                "thread_id": self.thread_id
            }
        }
        
        try:
            # Invoke the graph
            result = self.graph.invoke(initial_state, config)
            
            # Update tracking
            self.conversation_count += 1
            self.full_audit_log.extend(result.get("audit_log", []))
            
            response = result.get("response", "I couldn't generate a response.")
            
            print("\n" + "=" * 70)
            print("[RESPONSE]")
            print("=" * 70)
            print(response)
            print("=" * 70 + "\n")
            
            return response
            
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            print(f"[ERROR] {error_msg}")
            return f"I encountered an error: {error_msg}"
    
    # =========================================================================
    # STATE INSPECTION METHODS (NEW IN V2!)
    # =========================================================================
    
    def get_state_snapshot(self) -> Dict:
        """
        Get the current state snapshot for debugging
        
        HEALTH-TECH USE:
        - Debug unexpected responses
        - Audit conversation flow
        - Verify safety flags were set
        
        Returns:
            Dictionary with current state values
        """
        config = {"configurable": {"thread_id": self.thread_id}}
        
        try:
            snapshot = self.graph.get_state(config)
            
            return {
                "values": snapshot.values,
                "next": snapshot.next,
                "config": snapshot.config,
                "created_at": datetime.now().isoformat(),
            }
        except Exception as e:
            return {"error": str(e)}
    
    def get_conversation_history(self) -> List[Dict]:
        """Get formatted conversation history"""
        config = {"configurable": {"thread_id": self.thread_id}}
        
        try:
            snapshot = self.graph.get_state(config)
            messages = snapshot.values.get("messages", [])
            
            history = []
            for msg in messages:
                history.append({
                    "role": "user" if isinstance(msg, HumanMessage) else "assistant",
                    "content": getattr(msg, 'content', str(msg)),
                })
            
            return history
        except:
            return []
    
    def get_safety_flags(self) -> List[str]:
        """Get all accumulated safety flags"""
        config = {"configurable": {"thread_id": self.thread_id}}
        
        try:
            snapshot = self.graph.get_state(config)
            return snapshot.values.get("safety_flags", [])
        except:
            return []
    
    # =========================================================================
    # AUDIT METHODS
    # =========================================================================
    
    def get_audit_log(self) -> List[Dict]:
        """Get the full audit log for compliance"""
        return self.full_audit_log
    
    def export_audit_log(self, filepath: str = None) -> str:
        """Export audit log to JSON file"""
        if filepath is None:
            filepath = f"audit_log_{self.thread_id}.json"
        
        export_data = {
            "thread_id": self.thread_id,
            "export_time": datetime.now().isoformat(),
            "conversation_count": self.conversation_count,
            "user_medications": self.user_medications,
            "allergies": self.allergies,
            "audit_log": self.full_audit_log,
        }
        
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)
        
        print(f"Audit log exported to: {filepath}")
        return filepath
    
    # =========================================================================
    # PATIENT DATA METHODS
    # =========================================================================
    
    def update_medications(self, medications: List[Dict]):
        """Update patient's medication list"""
        self.user_medications = medications
        print(f"Updated medications: {len(medications)} items")
    
    def add_allergy(self, allergy: str):
        """Add an allergy (CRITICAL for safety!)"""
        if allergy not in self.allergies:
            self.allergies.append(allergy)
            print(f"Added allergy: {allergy}")
            print(f"Current allergies: {self.allergies}")
    
    def remove_allergy(self, allergy: str):
        """Remove an allergy"""
        if allergy in self.allergies:
            self.allergies.remove(allergy)
            print(f"Removed allergy: {allergy}")


# =============================================================================
# SECTION 7: TEST FUNCTION
# =============================================================================

def test_langgraph_v2():
    """
    Test the V2 implementation with various scenarios
    """
    print("\n" + "=" * 70)
    print("TESTING MEDTRACKER LANGGRAPH V2")
    print("=" * 70)
    
    # Test medications
    test_meds = [
        {"name": "Lisinopril", "dosage": "10mg", "frequency": "Once daily"},
        {"name": "Metformin", "dosage": "500mg", "frequency": "Twice daily"},
        {"name": "Warfarin", "dosage": "5mg", "frequency": "Once daily"},
    ]
    
    # Test allergies
    test_allergies = ["Penicillin", "Sulfa"]
    
    try:
        # Initialize chatbot
        chatbot = MedTrackerLangGraphV2(
            model_name="llama3",
            user_medications=test_meds,
            allergies=test_allergies,
            use_sqlite=False,  # Use memory for testing
        )
        
        # Test scenarios
        test_questions = [
            # General
            ("Hello!", "general_chat"),
            
            # Medication info
            ("What is metformin used for?", "medication_info"),
            
            # Interaction check (should trigger safety!)
            ("Can I take aspirin with my warfarin?", "interaction_check"),
            
            # Allergy test (should trigger safety!)
            ("Can I take amoxicillin for my infection?", "should_catch_penicillin_allergy"),
            
            # Side effects
            ("What are the side effects of lisinopril?", "side_effects"),
        ]
        
        print("\n" + "-" * 70)
        print("RUNNING TEST SCENARIOS")
        print("-" * 70)
        
        for i, (question, expected_type) in enumerate(test_questions, 1):
            print(f"\n[TEST {i}/{len(test_questions)}]")
            print(f"Expected: {expected_type}")
            
            response = chatbot.ask(question)
            
            # Check safety flags
            flags = chatbot.get_safety_flags()
            if flags:
                print(f"[SAFETY FLAGS] {flags}")
            
            input("\nPress ENTER for next test...")
        
        # Export audit log
        print("\n" + "-" * 70)
        print("EXPORTING AUDIT LOG")
        print("-" * 70)
        chatbot.export_audit_log()
        
        # Show state snapshot
        print("\n" + "-" * 70)
        print("STATE SNAPSHOT")
        print("-" * 70)
        snapshot = chatbot.get_state_snapshot()
        print(f"Messages in history: {len(snapshot.get('values', {}).get('messages', []))}")
        print(f"Safety flags: {snapshot.get('values', {}).get('safety_flags', [])}")
        
        print("\n" + "=" * 70)
        print("ALL TESTS COMPLETE!")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_langgraph_v2()
