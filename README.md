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

## What I Learned
- Chunk size significantly impacts retrieval quality (500 is my sweet spot)
- RAG reduces hallucination but doesn't eliminate it — retrieval can still fail
- Three key failure modes: retrieval miss, vague query, and zero overlap boundary failure