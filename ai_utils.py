"""
ai_utils.py — Groq-powered AI functions for the Study Assistant:
Summarize, Ask Questions (Q&A), and Quiz Generation (structured JSON).
"""

import json
import re

from langchain_groq import ChatGroq

DEFAULT_MODEL = "llama-3.3-70b-versatile"


def get_llm(temperature: float = 0.3):
    return ChatGroq(model=DEFAULT_MODEL, temperature=temperature)


def summarize_document(full_text: str) -> str:
    """
    Returns a plain-text summary of the whole document.
    Not structured JSON — this is meant to read like a normal summary.
    """
    llm = get_llm(temperature=0.3)

    prompt = (
        "You are a helpful study assistant. Summarize the following notes/document "
        "clearly and concisely for a student, in plain paragraphs (no JSON, no markdown "
        "headers) — cover the main ideas and key points a student should remember.\n\n"
        f"Document:\n{full_text}"
    )

    response = llm.invoke(prompt)
    return _extract_text(response.content)


def answer_question(context: str, question: str) -> str:
    """
    Returns a plain-text, grounded answer to the student's question based
    only on the retrieved context chunks.
    """
    llm = get_llm(temperature=0.2)

    prompt = (
        "You are a study assistant answering a student's question using only "
        "the context below, which was retrieved from their own notes. "
        "If the answer isn't in the context, say you don't know based on the "
        "provided notes — don't guess. Answer in plain text.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {question}"
    )

    response = llm.invoke(prompt)
    return _extract_text(response.content)


def generate_quiz(context: str, num_questions: int = 5) -> list[dict]:
    """
    Generates a quiz from the given context as structured JSON:
    [{ "question": str, "options": [str, str, str, str], "answer": str }, ...]

    Returns a Python list of dicts (already parsed) — the UI renders this
    into an interactive quiz, the raw JSON is never shown to the student.
    """
    llm = get_llm(temperature=0.4)

    prompt = (
        f"Create exactly {num_questions} multiple-choice quiz questions based only on "
        "the notes below. Each question must have exactly 4 options, with one correct "
        "answer matching one of the options exactly.\n\n"
        "Respond with ONLY a valid JSON array, no markdown, no code fences, no extra text. "
        "Format:\n"
        '[{"question": "...", "options": ["...", "...", "...", "..."], "answer": "..."}]\n\n'
        f"Notes:\n{context}"
    )

    response = llm.invoke(prompt)
    text = _extract_text(response.content)
    cleaned = re.sub(r"```json|```", "", text).strip()

    try:
        quiz = json.loads(cleaned)
        if not isinstance(quiz, list):
            raise ValueError("Model did not return a JSON array.")
        return quiz
    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(f"Could not parse quiz output as JSON: {e}")


def _extract_text(content) -> str:
    """
    Handles both plain-string and structured-block response formats
    (some models/providers return content as a list of blocks).
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "") for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return str(content)
