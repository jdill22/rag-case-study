# RAG Case Study
A production-grade retrieval-augmented generation (RAG) pipeline built with Python, ChromaDB, and the Anthropic API — evolved from basic RAG to Advanced RAG with hybrid search and re-ranking.

## What It Does
Loads real PM job description PDFs into a vector database, then answers questions grounded in those documents using Claude as the LLM. The pipeline implements hybrid search (BM25 + semantic) and cross-encoder re-ranking to surface the most relevant context before generation.

## Problem It Solves
LLMs have knowledge cutoff dates, no access to private data, and can hallucinate confidently. RAG solves this by retrieving relevant document chunks and injecting them as context before generation — grounding the model's response in real, specific information. Advanced RAG goes further by combining lexical and semantic search to catch what either method alone would miss.

## Tech Stack
- Python
- LangChain
- HuggingFace Embeddings
- ChromaDB (in-memory vector store)
- rank_bm25 (lexical search)
- sentence-transformers (cross-encoder re-ranking)
- Anthropic API (Claude)

## How to Run
1. Clone the repo
2. Create a virtual environment: `python -m venv venv`
3. Activate it: `source venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Add your Anthropic API key to a `.env` file: `ANTHROPIC_API_KEY=your_key`
6. Run: `python rag_case_study.py`

## Advanced RAG Pipeline — Full Flow
1. **Ingestion** — Load PDFs, chunk with overlap (chunk_size=500, chunk_overlap=50)
2. **Vector Index** — Embed chunks with HuggingFace, store in ChromaDB for semantic search
3. **Text Index** — Store raw chunk text in BM25 index for lexical search
4. **Hybrid Search** — Run semantic search and BM25 in parallel, retrieve top chunks from each
5. **Combine + Deduplicate** — Merge both result sets, remove duplicate chunks
6. **Re-ranking** — Score combined chunks against the query using a cross-encoder model
7. **Generation** — Send top 3 re-ranked chunks as context to Claude, generate grounded response

## Hybrid Search
Semantic search finds results by meaning — it catches relevance even when words differ. But it misses exact keyword matches when meaning is ambiguous. BM25 lexical search catches exact terms but misses meaning when words vary.

Neither is complete alone. Running both in parallel covers each other's blind spots.

**Semantic search path:** chunks → embeddings → ChromaDB → cosine similarity
**Lexical search path:** chunks → raw text → BM25 index → keyword scoring

Results are combined and deduplicated before re-ranking.

## Re-ranking
After hybrid search retrieves the top chunks, a cross-encoder re-ranks them based on how well each chunk answers the original query — not just keyword or semantic similarity.

The cross-encoder scores each (query, chunk) pair together, producing a more accurate relevance score than either retrieval method alone. Only the top 3 chunks go to the LLM.

**Why it matters:** Re-ranking is a quality gate. It ensures the LLM gets the most relevant context, reducing the risk of a confident but wrong answer.

## PM Metrics
Defined for CareerAI — the job application agent this pipeline supports:

| Metric | Value | Reasoning |
|--------|-------|-----------|
| North Star | Qualified applications per user per day | Measures real user value, not technical performance |
| Acceptable hallucination rate | < 3% | Job applications affect livelihoods — errors have real consequences |
| Confidence threshold | 0.5 (ChromaDB distance) | Below 0.5 = answer directly. Above 0.5 = add caveat or fallback |
| Cost at 10K users | ~$7.50/day | Avg tokens per query × price per token × queries per day |

## Chunking Experiments
Tested three chunk sizes on the same query: "What skills are required for this role?"

**1. chunk_size=200 (50 chunks)**
Result: Vague, incomplete, text cut off mid-sentence. Too small — loses context.

**2. chunk_size=500 (18 chunks)**
Result: Clean, specific, complete. Sweet spot for this dataset.

**3. chunk_size=1000 (9 chunks)**
Result: Comprehensive but fewer chunks means less precision on targeted questions.

**Decision:** 500 is my default starting point going forward.

## Failure Modes (With Examples)
**1. Retrieval Miss**
Query had no relevant context in the DB. Model said "I don't know" then answered from general knowledge anyway — dangerous when the answer isn't obvious.

**2. Vague Query**
Weak chunks retrieved from wrong context. Model gave an irrelevant answer and asked for clarification at the END instead of the beginning.

**3. Zero Overlap Boundary Failure**
With chunk_overlap=0, chunk count dropped from 71 to 69. Minimal impact on well-structured docs but significant on dense unstructured text.

**4. Boilerplate Pollution**
Chunks containing headers, footers, salary ranges, and legal disclaimers scored well in retrieval despite being irrelevant to the query. Data cleaning before ingestion is a product decision — it directly determines answer quality for users.

## What I Learned
- Chunk size significantly impacts retrieval quality (500 is my sweet spot)
- RAG reduces hallucination but doesn't eliminate it — retrieval can still fail
- Semantic search alone is incomplete — hybrid search covers the blind spots
- Re-ranking improves context quality but can only work with what you give it — garbage in, garbage out
- A decent-looking LLM answer doesn't mean retrieval is working — you need an eval dataset to know for sure
- Boilerplate pollution is a product decision, not just an engineering cleanup task
- Three signals tell you if your RAG system is working: eval dataset, confidence threshold, and North Star metric

## Portfolio Artifacts
- [Retrieval Score Case Study](Retrieval_Score_CaseStudy_JoshDillingham.docx) — 
Three retrieval experiments documenting score logging, boilerplate pollution, 
and chunking tradeoffs across chunk sizes 200 and 500.
