"""
Medication RAG Chatbot Engine - OLLAMA ONLY
Fixed version with user medications support
"""

from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.llms import Ollama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from typing import List, Dict
from .medication_knowledge import MedicationKnowledgeBase


class MedicationRAGChatbot:
    """RAG Chatbot using Ollama"""
    
    def __init__(self, model_name="llama3", user_medications=None):
        print("🚀 Initializing Medication RAG Chatbot with Ollama...")
        
        print("  📊 Loading embedding model...")
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        
        print("  💾 Setting up vector database...")
        self.vectorstore = Chroma(
            collection_name="medication_knowledge",
            embedding_function=self.embeddings,
            persist_directory="./chroma_db"
        )
        
        print(f"  🤖 Setting up Ollama ({model_name})...")
        self.llm = Ollama(model=model_name, temperature=0.1)
        
        self.user_medications = user_medications
        
        print("  ⛓️  Building RAG chain...")
        
        # 🎓 RETRIEVAL STRATEGIES
        # Similarity: Find most similar docs (basic)
        # MMR: Find relevant AND diverse docs (better for drug interactions)
        print("  🔍 Setting up retrieval strategies...")
        
        self.retriever_similarity = self.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 5}
        )
        
        self.retriever_mmr = self.vectorstore.as_retriever(
            search_type="mmr",
            search_kwargs={
                "k": 5,
                "fetch_k": 10,
                "lambda_mult": 0.5  # Balance: 0=diversity, 1=similarity
            }
        )
        
        # Default to MMR (better for medical queries)
        self.retriever = self.retriever_mmr
        
        self.rag_chain = self._create_rag_chain_with_db(user_medications)
        
        self.knowledge_base = MedicationKnowledgeBase()
        
        print("✅ RAG Chatbot ready!")
    
    def _create_rag_chain_with_db(self, user_medications=None):
        """Create RAG chain with direct database access for user meds"""
        
        template = """You are a medication assistant. 

THE USER'S COMPLETE MEDICATION LIST:
{user_meds}

Question: {question}

INSTRUCTIONS:
- When asked about current medications, copy the EXACT list from above
- Don't tell the user that you're copying the list as given to you, or any variation
- Do NOT add medications not in the list
- Do NOT make up medications
- For medical advice, say "Consult your doctor"

Answer:"""

        prompt = ChatPromptTemplate.from_template(template)
        
        def format_user_meds(_):
            print(f"\n🔍 format_user_meds called!")
            print(f"🔍 user_medications is None: {user_medications is None}")
            print(f"🔍 user_medications length: {len(user_medications) if user_medications else 0}")
            
            if not user_medications:
                return "No medications found."
            
            formatted = []
            for med in user_medications:
                print(f"🔍 Formatting: {med['name']}")
                med_line = f"- {med['name']}: {med['dosage']}, {med['frequency']}"
                if med.get('notes'):
                    med_line += f", Notes: {med['notes']}"
                formatted.append(med_line)
            
            result = "\n".join(formatted)
            print(f"🔍 Final formatted result ({len(result)} chars):")
            print(result)
            print("🔍 End of formatted meds\n")
            return result
        
        rag_chain = (
            {
                "user_meds": lambda x: format_user_meds(x),
                "context": self.retriever | self._format_docs, # Uses MMR retriever
                "question": RunnablePassthrough()
            }
            | prompt
            | self.llm
            | StrOutputParser()
        )
        
        return rag_chain
    
    def _format_docs(self, docs):
        return "\n\n".join(doc.page_content for doc in docs)
    
    def add_medication_to_knowledge_base(self, medication_name: str):
        """
        🎓 INDEXING: Add medication to vector store with metadata
        
        Metadata is CRITICAL in health-tech for:
        - Audit trails (where did this info come from?)
        - Filtering (only search FDA sources, etc.)
        - Debugging (why did the LLM say that?)
        """
        print(f"📚 Adding {medication_name} to knowledge base...")
        
        drug_info = self.knowledge_base.search_drug(medication_name)
        
        if drug_info['success']:
            formatted_text = self.knowledge_base.format_for_rag(drug_info)
            
            interactions = self.knowledge_base.get_drug_interactions(medication_name)
            if interactions['success']:
                formatted_text += f"\n\n{self.knowledge_base.format_for_rag(interactions)}"
            
            # 🎓 INDEXING with metadata - track the source!
            self.vectorstore.add_texts(
                texts=[formatted_text],
                metadatas=[{
                    "drug_name": medication_name,
                    "source": "RxNorm_API",  # 🏥 Audit trail!
                    "indexed_at": str(__import__('datetime').datetime.now())
                }]
            )
            
            print(f"  ✅ Added {medication_name} with metadata tracking")
            return True
        else:
            print(f"  ❌ Could not add {medication_name}: {drug_info.get('error')}")
            return False
    
    def ask_question(self, question: str) -> str:
        print(f"\n❓ Question: {question}")
        answer = self.rag_chain.invoke(question)
        print(f"💡 Answer: {answer}")
        return answer
    
    def add_user_medications_to_kb(self, medications: List[Dict]):
        """Add user medications to vector store"""
        print(f"\n📋 Adding {len(medications)} user medications to knowledge base...")
        
        for med in medications:
            med_name = med.get('name')
            if med_name:
                parts = [f"You are taking {med_name}."]
                
                if med.get('dosage'):
                    parts.append(f"The dosage is {med.get('dosage')}.")
                
                if med.get('frequency'):
                    parts.append(f"Take it {med.get('frequency').lower()}.")
                
                if med.get('notes'):
                    notes = med.get('notes')
                    if 'food' in notes.lower():
                        parts.append(f"{med_name} should be taken with food.")
                    if 'morning' in notes.lower():
                        parts.append(f"Take {med_name} in the morning.")
                    if 'night' in notes.lower() or 'bed' in notes.lower():
                        parts.append(f"Take {med_name} at night.")
                    parts.append(f"Additional notes: {notes}")
                
                user_med_text = " ".join(parts)
                
                self.vectorstore.add_texts(
                    texts=[user_med_text],
                    metadatas=[{
                        "source": "user_medication",
                        "drug_name": med_name,
                        "med_id": med.get('id')
                    }]
                )

    print("  ✅ User medications added to knowledge base!")

    def ask_question_with_debug(self, question: str, use_mmr: bool = True) -> str:
        """
        🎓 LEARNING VERSION: Shows retrieval step before answering
        
        This helps you SEE what the retriever finds!
        Health-Tech Learning: Always verify what info the LLM receives.
        """
        print(f"\n{'='*50}")
        print(f"❓ Question: {question}")
        print(f"📊 Strategy: {'MMR (diverse)' if use_mmr else 'Similarity (basic)'}")
        print(f"{'='*50}")
        
        # Switch retriever based on preference
        if use_mmr:
            self.retriever = self.retriever_mmr
        else:
            self.retriever = self.retriever_similarity
        
        # 🔍 RETRIEVAL STEP - See what docs are found
        print(f"\n🔍 RETRIEVAL: Finding relevant documents...")
        retrieved_docs = self.retriever.invoke(question)
        print(f"   Found {len(retrieved_docs)} documents:")
        
        for i, doc in enumerate(retrieved_docs):
            preview = doc.page_content[:80].replace('\n', ' ')
            source = doc.metadata.get('source', 'unknown')
            print(f"   {i+1}. [{source}] {preview}...")
        
        # 🧠 GENERATION STEP - Rebuild chain with current retriever
        self.rag_chain = self._create_rag_chain_with_db(self.user_medications)
        
        print(f"\n🧠 GENERATION: Sending to LLM...")
        answer = self.rag_chain.invoke(question)
        
        print(f"\n💬 ANSWER:")
        print(f"   {answer}")
        print(f"{'='*50}\n")
        
        return answer
