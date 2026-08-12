"""
rag_utils.py — Document loading, chunking, embedding, and retrieval helpers
for the AI Study Assistant's document-based features (Summarize, Q&A, Quiz).

This mirrors the RAG pattern from the Week 1-2 project: local embeddings
(no API cost), FAISS for retrieval, Groq for generation.
"""

import os
import tempfile

from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

SUPPORTED_EXTENSIONS = [".pdf", ".docx", ".txt"]
MAX_FILE_MB = 15


def load_document(uploaded_file):
    """
    Takes a Streamlit UploadedFile, writes it to a temp path, loads it with
    the correct LangChain loader based on extension, and returns the list
    of Document objects. Raises ValueError with a user-facing message on
    any problem (bad extension, empty file, oversized file).
    """
    size_mb = uploaded_file.size / (1024 * 1024)
    if size_mb > MAX_FILE_MB:
        raise ValueError(f"File is {size_mb:.1f} MB — please upload a file under {MAX_FILE_MB} MB.")

    suffix = os.path.splitext(uploaded_file.name)[1].lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {suffix}. Please upload PDF, DOCX, or TXT.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getvalue())
        tmp_path = tmp.name

    try:
        if suffix == ".pdf":
            loader = PyPDFLoader(tmp_path)
        elif suffix == ".docx":
            loader = Docx2txtLoader(tmp_path)
        else:
            loader = TextLoader(tmp_path, encoding="utf-8")

        documents = loader.load()

        if not documents or all(not d.page_content.strip() for d in documents):
            raise ValueError("No readable text found in this file (it may be scanned/image-only).")

        return documents
    finally:
        os.remove(tmp_path)


def get_embeddings():
    """Local, free embeddings model — no API key or cost."""
    return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")


def build_vectorstore(documents):
    """
    Splits documents into overlapping chunks and builds a FAISS index.
    Returns (vectorstore, chunk_count) so the UI can show how many chunks
    the document was split into.
    """
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)
    chunks = splitter.split_documents(documents)

    embeddings = get_embeddings()
    vectorstore = FAISS.from_documents(chunks, embeddings)

    return vectorstore, len(chunks)


def get_full_text(documents, max_chars: int = 12000) -> str:
    """
    Concatenates all document content into a single string, capped at
    max_chars, for use in the Summarize feature (which wants the whole
    document, not just a retrieved slice).
    """
    full_text = "\n\n".join(d.page_content for d in documents)
    return full_text[:max_chars]


def retrieve_context(vectorstore, query: str, k: int = 4) -> str:
    """
    Retrieves the top-k relevant chunks for a query and joins them into a
    single context string, for use in the Q&A and Quiz features.
    """
    docs = vectorstore.similarity_search(query, k=k)
    return "\n\n".join(d.page_content for d in docs)
