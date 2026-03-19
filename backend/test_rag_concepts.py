import sys
import os

# Add parent directory to path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_community.llms import Ollama
from datetime import datetime


def test_embedding():
    """
    🎓 TEST 1: EMBEDDING
    ====================
    See how text becomes numbers (vectors)!
    
    WHY THIS MATTERS IN HEALTH-TECH:
    "Blood thinner" and "anticoagulant" become SIMILAR vectors
    So patients can search in their own words!
    """
    print("\n" + "="*60)
    print("🎓 TEST 1: EMBEDDING")
    print("="*60)
    print("Converting text to vectors (numbers)...\n")
    
    # Load the embedding model
    print("📊 Loading embedding model...")
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )
    print("✅ Model loaded!\n")
    
    # Test texts - medical terms a patient might use
    test_texts = [
        "blood pressure medication",
        "lisinopril",
        "heart medicine",
        "banana",  # Unrelated - should be far away!
    ]
    
    print("🔬 EMBEDDING DEMO:")
    print("-"*40)
    
    vectors = {}
    for text in test_texts:
        vector = embeddings.embed_query(text)
        vectors[text] = vector
        
        # Show first 5 numbers of the vector
        print(f"\n'{text}'")
        print(f"   Vector length: {len(vector)} dimensions")
        print(f"   First 5 values: [{vector[0]:.4f}, {vector[1]:.4f}, {vector[2]:.4f}, {vector[3]:.4f}, {vector[4]:.4f}, ...]")
    
    # Calculate similarity between vectors
    print("\n" + "-"*40)
    print("📏 SIMILARITY CHECK:")
    print("-"*40)
    
    def cosine_similarity(v1, v2):
        """Calculate how similar two vectors are (0 to 1)"""
        dot_product = sum(a * b for a, b in zip(v1, v2))
        magnitude1 = sum(a * a for a in v1) ** 0.5
        magnitude2 = sum(b * b for b in v2) ** 0.5
        return dot_product / (magnitude1 * magnitude2)
    
    # Compare similarities
    sim_bp_lisinopril = cosine_similarity(vectors["blood pressure medication"], vectors["lisinopril"])
    sim_bp_heart = cosine_similarity(vectors["blood pressure medication"], vectors["heart medicine"])
    sim_bp_banana = cosine_similarity(vectors["blood pressure medication"], vectors["banana"])
    
    print(f"\n'blood pressure medication' vs 'lisinopril':  {sim_bp_lisinopril:.4f} ← SIMILAR! ✅")
    print(f"'blood pressure medication' vs 'heart medicine': {sim_bp_heart:.4f} ← SIMILAR! ✅")
    print(f"'blood pressure medication' vs 'banana':        {sim_bp_banana:.4f} ← DIFFERENT! ✅")
    
    print("\n💡 HEALTH-TECH INSIGHT:")
    print("   Even though 'lisinopril' doesn't contain 'blood pressure',")
    print("   the embedding model KNOWS they're related!")
    print("   This is why patients can search in their own words.")
    
    return embeddings


def test_indexing(embeddings):
    """
    🎓 TEST 2: INDEXING
    ===================
    Store documents in the vector database
    
    WHY THIS MATTERS IN HEALTH-TECH:
    Fast search through thousands of medications!
    """
    print("\n" + "="*60)
    print("🎓 TEST 2: INDEXING")
    print("="*60)
    print("Storing documents in ChromaDB...\n")
    
    # Create a test vector store (separate from your main one)
    print("💾 Creating test vector store...")
    test_vectorstore = Chroma(
        collection_name="test_medications",
        embedding_function=embeddings,
        persist_directory="./test_chroma_db"
    )
    
    # Sample medication documents to index
    test_documents = [
        {
            "text": "Lisinopril is used to treat high blood pressure (hypertension). It is an ACE inhibitor.",
            "metadata": {"drug_name": "Lisinopril", "source": "FDA", "type": "indication"}
        },
        {
            "text": "Common side effects of Lisinopril include dizziness, headache, and dry cough.",
            "metadata": {"drug_name": "Lisinopril", "source": "FDA", "type": "side_effects"}
        },
        {
            "text": "Metformin is used to treat type 2 diabetes. Take with food to reduce stomach upset.",
            "metadata": {"drug_name": "Metformin", "source": "FDA", "type": "indication"}
        },
        {
            "text": "Do not take Metformin with alcohol. May cause lactic acidosis in rare cases.",
            "metadata": {"drug_name": "Metformin", "source": "FDA", "type": "warning"}
        },
        {
            "text": "Aspirin is used for pain relief and to prevent heart attacks. Take with food.",
            "metadata": {"drug_name": "Aspirin", "source": "FDA", "type": "indication"}
        },
    ]
    
    print(f"📄 Indexing {len(test_documents)} documents...\n")
    
    for i, doc in enumerate(test_documents):
        print(f"   {i+1}. Adding: '{doc['text'][:50]}...'")
        print(f"      Metadata: {doc['metadata']}")
        
        test_vectorstore.add_texts(
            texts=[doc["text"]],
            metadatas=[doc["metadata"]]
        )
    
    # Verify indexing
    collection = test_vectorstore._collection
    count = collection.count()
    
    print(f"\n✅ INDEXING COMPLETE!")
    print(f"   Total documents in vector store: {count}")
    
    print("\n💡 HEALTH-TECH INSIGHT:")
    print("   Each document has METADATA (drug_name, source, type)")
    print("   This creates an AUDIT TRAIL - critical for healthcare!")
    print("   You can always trace WHERE information came from.")
    
    return test_vectorstore


def test_retrieval_strategies(vectorstore):
    """
    🎓 TEST 3: RETRIEVAL STRATEGIES
    ================================
    Compare Similarity vs MMR vs Threshold
    
    WHY THIS MATTERS IN HEALTH-TECH:
    Different questions need different strategies!
    """
    print("\n" + "="*60)
    print("🎓 TEST 3: RETRIEVAL STRATEGIES")
    print("="*60)
    
    # Create three different retrievers
    retriever_similarity = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 3}
    )
    
    retriever_mmr = vectorstore.as_retriever(
        search_type="mmr",
        search_kwargs={"k": 3, "fetch_k": 5, "lambda_mult": 0.5}
    )
    
    retriever_threshold = vectorstore.as_retriever(
        search_type="similarity_score_threshold",
        search_kwargs={"k": 3, "score_threshold": 0.3}
    )
    
    # Test query
    test_query = "What are the side effects of my blood pressure medication?"
    
    print(f"\n🔍 TEST QUERY: '{test_query}'")
    print("="*60)
    
    # Strategy 1: Similarity
    print("\n📌 STRATEGY 1: SIMILARITY SEARCH")
    print("-"*40)
    print("   How it works: Find the K most similar documents")
    print("   Best for: Simple, direct questions")
    print()
    
    docs_sim = retriever_similarity.invoke(test_query)
    print(f"   Results ({len(docs_sim)} documents):")
    for i, doc in enumerate(docs_sim):
        drug = doc.metadata.get('drug_name', 'Unknown')
        doc_type = doc.metadata.get('type', 'unknown')
        preview = doc.page_content[:60]
        print(f"   {i+1}. [{drug} - {doc_type}] {preview}...")
    
    # Strategy 2: MMR
    print("\n📌 STRATEGY 2: MMR (Maximal Marginal Relevance)")
    print("-"*40)
    print("   How it works: Find relevant AND diverse documents")
    print("   Best for: Drug interactions (need info about MULTIPLE drugs)")
    print()
    
    docs_mmr = retriever_mmr.invoke(test_query)
    print(f"   Results ({len(docs_mmr)} documents):")
    for i, doc in enumerate(docs_mmr):
        drug = doc.metadata.get('drug_name', 'Unknown')
        doc_type = doc.metadata.get('type', 'unknown')
        preview = doc.page_content[:60]
        print(f"   {i+1}. [{drug} - {doc_type}] {preview}...")
    
    # Strategy 3: Threshold
    print("\n📌 STRATEGY 3: SIMILARITY WITH THRESHOLD")
    print("-"*40)
    print("   How it works: Only return docs above a similarity score")
    print("   Best for: Safety-critical queries (better no answer than wrong answer)")
    print()
    
    docs_threshold = retriever_threshold.invoke(test_query)
    print(f"   Results ({len(docs_threshold)} documents):")
    for i, doc in enumerate(docs_threshold):
        drug = doc.metadata.get('drug_name', 'Unknown')
        doc_type = doc.metadata.get('type', 'unknown')
        preview = doc.page_content[:60]
        print(f"   {i+1}. [{drug} - {doc_type}] {preview}...")
    
    # Bonus: Show actual scores
    print("\n📊 BONUS: Similarity Scores (Lower = More Similar in ChromaDB)")
    print("-"*40)
    docs_with_scores = vectorstore.similarity_search_with_score(test_query, k=5)
    for i, (doc, score) in enumerate(docs_with_scores):
        drug = doc.metadata.get('drug_name', 'Unknown')
        print(f"   {i+1}. Score: {score:.4f} - {drug}: {doc.page_content[:40]}...")
    
    print("\n💡 HEALTH-TECH INSIGHT:")
    print("   - Use SIMILARITY for simple lookups")
    print("   - Use MMR when you need info about multiple drugs")
    print("   - Use THRESHOLD when wrong info could harm patient")
    
    return retriever_mmr


def test_generation_stuffing(vectorstore, retriever):
    """
    🎓 TEST 4: GENERATION STUFFING
    ==============================
    Put all retrieved docs into one prompt
    
    WHY THIS MATTERS IN HEALTH-TECH:
    LLM sees ALL relevant drug info at once for complete answers
    """
    print("\n" + "="*60)
    print("🎓 TEST 4: GENERATION STUFFING")
    print("="*60)
    
    print("\n📝 WHAT IS 'STUFFING'?")
    print("-"*40)
    print("   Take ALL retrieved documents and 'stuff' them into")
    print("   a single prompt. The LLM sees everything at once.")
    print()
    
    # Sample user medications
    user_medications = [
        {"name": "Lisinopril", "dosage": "10mg", "frequency": "Once daily"},
        {"name": "Metformin", "dosage": "500mg", "frequency": "Twice daily"},
    ]
    
    # Test question
    question = "What should I know about my medications?"
    
    print(f"❓ QUESTION: '{question}'")
    print()
    
    # Step 1: Retrieve documents
    print("🔍 STEP 1: RETRIEVE relevant documents")
    print("-"*40)
    retrieved_docs = retriever.invoke(question)
    print(f"   Retrieved {len(retrieved_docs)} documents")
    for i, doc in enumerate(retrieved_docs):
        print(f"   {i+1}. {doc.page_content[:50]}...")
    print()
    
    # Step 2: Format user medications
    print("📋 STEP 2: FORMAT user medications")
    print("-"*40)
    user_meds_text = ""
    for med in user_medications:
        user_meds_text += f"- {med['name']}: {med['dosage']}, {med['frequency']}\n"
    print(user_meds_text)
    
    # Step 3: Format retrieved documents (STUFFING!)
    print("📚 STEP 3: 'STUFF' documents into context")
    print("-"*40)
    context = "\n\n".join([doc.page_content for doc in retrieved_docs])
    print(f"   Combined {len(retrieved_docs)} docs into {len(context)} characters")
    print()
    
    # Step 4: Build the final prompt
    print("📝 STEP 4: BUILD final prompt (THE STUFFING!)")
    print("-"*40)
    
    final_prompt = f"""You are a medication assistant.

USER'S MEDICATIONS:
{user_meds_text}

RELEVANT INFORMATION (STUFFED DOCUMENTS):
{context}

QUESTION: {question}

Answer:"""
    
    print("   FINAL PROMPT PREVIEW:")
    print("   " + "~"*50)
    # Show truncated version
    lines = final_prompt.split('\n')
    for line in lines[:15]:
        print(f"   {line}")
    print("   ...")
    print("   " + "~"*50)
    print()
    
    # Step 5: Send to LLM (if Ollama is running)
    print("🧠 STEP 5: GENERATE answer from LLM")
    print("-"*40)
    
    try:
        print("   Connecting to Ollama (llama3)...")
        llm = Ollama(model="llama3", temperature=0.1)
        
        print("   Sending stuffed prompt to LLM...")
        answer = llm.invoke(final_prompt)
        
        print("\n💬 LLM ANSWER:")
        print("   " + "-"*40)
        for line in answer.split('\n'):
            print(f"   {line}")
        print("   " + "-"*40)
        
    except Exception as e:
        print(f"   ⚠️ Could not connect to Ollama: {e}")
        print("   Make sure Ollama is running: ollama serve")
        print("   And llama3 is available: ollama run llama3")
    
    print("\n💡 HEALTH-TECH INSIGHT:")
    print("   'Stuffing' lets the LLM see ALL relevant info at once.")
    print("   This is crucial for drug interactions - you need to see")
    print("   info about BOTH drugs together to spot problems!")


def cleanup():
    """Remove test database"""
    import shutil
    if os.path.exists("./test_chroma_db"):
        shutil.rmtree("./test_chroma_db")
        print("\n🧹 Cleaned up test database")


def main():
    """
    Run all tests in sequence
    """
    print("\n" + "🏥"*30)
    print("     RAG CONCEPTS TESTER FOR MEDTRACKER")
    print("🏥"*30)
    print(f"\n⏰ Started at: {datetime.now().strftime('%H:%M:%S')}")
    print("\nThis will demonstrate each RAG concept with your actual code!")
    print("Watch the output to SEE how each concept works.\n")
    
    input("Press ENTER to start TEST 1: EMBEDDING...")
    
    # Test 1: Embedding
    embeddings = test_embedding()
    
    input("\nPress ENTER to start TEST 2: INDEXING...")
    
    # Test 2: Indexing
    vectorstore = test_indexing(embeddings)
    
    input("\nPress ENTER to start TEST 3: RETRIEVAL STRATEGIES...")
    
    # Test 3: Retrieval
    retriever = test_retrieval_strategies(vectorstore)
    
    input("\nPress ENTER to start TEST 4: GENERATION STUFFING...")
    
    # Test 4: Generation Stuffing
    test_generation_stuffing(vectorstore, retriever)
    
    # Cleanup
    cleanup()
    
    print("\n" + "="*60)
    print("✅ ALL TESTS COMPLETE!")
    print("="*60)
    print("\nYou've now seen:")
    print("   1. ✅ Embedding - Text → Vectors (numbers)")
    print("   2. ✅ Indexing - Storing in ChromaDB with metadata")
    print("   3. ✅ Retrieval - Similarity vs MMR vs Threshold")
    print("   4. ✅ Generation Stuffing - All docs in one prompt")
    print(f"\n⏰ Finished at: {datetime.now().strftime('%H:%M:%S')}")


if __name__ == "__main__":
    main()