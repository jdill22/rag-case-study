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
qa_chain = RetrievalQA.from_chain_type(llm=llm, retriever=vectorstore.as_retriever())

questions = [
    "What skills are required for this role?",
]

for question in questions:
    print(f"\nQ: {question}")
    answer = qa_chain.invoke(question)
    print(f"A: {answer['result']}")