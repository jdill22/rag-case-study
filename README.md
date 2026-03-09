# RAG Case Study

A retrieval-augmented generation (RAG) pipeline built with Python, ChromaDB, and the Anthropic API.

## What It Does
Loads real PM job description PDFs and a private product PRD into a vector database, then answers questions grounded in those documents using Claude as the LLM.

## Problem It Solves
LLMs have knowledge cutoff dates, no access to private data, and can hallucinate confidently. RAG solves this by retrieving relevant document chunks and injecting them as context before generation — grounding the model's response in real, specific information.

## Tech Stack
- Python
- LangChain
- HuggingFace Embeddings
- ChromaDB (in-memory vector store)
- Anthropic API (Claude)

## How to Run
1. Clone the repo
2. Create a virtual environment: `python -m venv venv`
3. Activate it: `source venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Add your Anthropic API key to a `.env` file: `ANTHROPIC_API_KEY=your_key`
6. Run: `python rag_case_study.py`

## Chunking Experiments

Tested three chunk sizes on the same query: "What skills are required for this role?"

**chunk_size=200 (50 chunks)**
Result: Vague, incomplete, text cut off mid-sentence. Too small — loses context.

**chunk_size=500 (18 chunks)**
Result: Clean, specific, complete. Sweet spot for this dataset.

**chunk_size=1000 (9 chunks)**
Result: Comprehensive but fewer chunks means less precision on targeted questions.

**Decision:** 500 is my default starting point going forward.

## Failure Modes (With Examples)

**1. Retrieval Miss**
Query had no relevant context in the DB. Model said "I don't know" then answered from general knowledge anyway — dangerous when the answer isn't obvious.

**2. Vague Query**
Weak chunks retrieved from wrong context. Model gave an irrelevant answer and asked for clarification at the END instead of the beginning.

**3. Zero Overlap Boundary Failure**
With chunk_overlap=0, chunk count dropped from 71 to 69. Minimal impact on well-structured docs but significant on dense unstructured text.

## What I Learned
- Chunk size significantly impacts retrieval quality (500 is my sweet spot)
- RAG reduces hallucination but doesn't eliminate it — retrieval can still fail
- Three key failure modes: retrieval miss, vague query, and zero overlap boundary failure
