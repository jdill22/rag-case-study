from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_anthropic import ChatAnthropic
from dotenv import load_dotenv

load_dotenv()

# Load all three PDFs
files = [
    "data/Product Manager II, Content Studio, NotebookLM-Labs.pdf",
    "data/Product Manager, Business AI.pdf",
]

all_chunks = []
splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)

for file in files:
    loader = PyPDFLoader(file)
    pages = loader.load()
    chunks = splitter.split_documents(pages)
    all_chunks.extend(chunks)
    print(f"Loaded: {file} — {len(chunks)} chunks")

print(f"\nTotal chunks: {len(all_chunks)}")

# Store everything together
embeddings = HuggingFaceEmbeddings()
vectorstore = Chroma.from_documents(all_chunks, embeddings)

# BM25 index — builds a lexical search index from raw chunk text
# Runs in parallel with semantic search to cover keyword matching gaps

#  BM25 index — lexical search
from rank_bm25 import BM25Okapi
import numpy as np

chunk_texts = [chunk.page_content for chunk in all_chunks]
tokenized_chunks = [text.split() for text in chunk_texts]
bm25 = BM25Okapi(tokenized_chunks)

# Define query here so both searches can use it
query = "What are the key responsibilities of this role?"

# Run BM25 search
tokenized_query = query.split()
bm25_scores = bm25.get_scores(tokenized_query)
top_bm25_indices = np.argsort(bm25_scores)[::-1][:4]

print("\n--- BM25 Results ---")
for i, idx in enumerate(top_bm25_indices):
    print(f"Chunk {i+1} | BM25 Score: {bm25_scores[idx]:.4f}")
    print(f"Content: {chunk_texts[idx][:150]}")
    print()

# Ask your questions
llm = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0.4)

# Semantic search
docs_with_scores = vectorstore.similarity_search_with_score(query, k=4)

# Log semantic scores
print(f"\nQuery: {query}")
print(f"\n--- Retrieved Chunks with Scores ---")
for i, (doc, score) in enumerate(docs_with_scores):
    print(f"\nChunk {i+1} | Score: {score:.4f}")
    print(f"Source: {doc.metadata.get('source', 'unknown')}")
    print(f"Content: {doc.page_content[:200]}...")

# Build context and send to LLM
context = "\n\n".join([doc.page_content for doc, _ in docs_with_scores])
prompt = f"Context:\n{context}\n\nQuestion: {query}\nAnswer:"
answer = llm.predict(prompt)
print(f"\nAnswer: {answer}")