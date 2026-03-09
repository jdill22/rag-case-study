from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_anthropic import ChatAnthropic
from langchain.chains import RetrievalQA
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

# Ask your questions
llm = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0.4)

# Step 1: Retrieve chunks with scores
query = "What skills are required for this role?"

docs_with_scores = vectorstore.similarity_search_with_score(query, k=4)

# Step 2: Log the scores
print(f"\nQuery: {query}")
print(f"\n--- Retrieved Chunks with Scores ---")
for i, (doc, score) in enumerate(docs_with_scores):
    print(f"\nChunk {i+1} | Score: {score:.4f}")
    print(f"Source: {doc.metadata.get('source', 'unknown')}")
    print(f"Content: {doc.page_content[:200]}...")

# Step 3: Build context and send to LLM
context = "\n\n".join([doc.page_content for doc, _ in docs_with_scores])
prompt = f"Context:\n{context}\n\nQuestion: {query}\nAnswer:"
answer = llm.predict(prompt)
print(f"\nAnswer: {answer}")