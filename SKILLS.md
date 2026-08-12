# SKILLS.md — AI Study Assistant (Capstone)

Reference document: tools, concepts, and terms used in this project, so any future session (or teammate) can understand the stack without re-explaining from scratch.

---

## Frontend / App

**Streamlit** — Python web app framework, chosen for consistency with earlier weeks' projects and speed of building a working UI without separate frontend/backend code.

**st.session_state** — Streamlit's way of holding data (like the uploaded document's index, or the logged-in student's email) across reruns of the script, since Streamlit reruns the whole script on every interaction by default.

**st_autorefresh (streamlit-autorefresh package)** — small third-party component that triggers the Streamlit script to rerun on an interval (e.g. every 10-30 seconds) without the user manually refreshing. Used to keep the live timer/countdown updating while the tab stays open.

---

## Document AI (RAG — reused pattern from Weeks 1-2)

**Loaders** — `PyPDFLoader` / `Docx2txtLoader` / `TextLoader`, parse the uploaded file into text.
**Chunking** — `RecursiveCharacterTextSplitter`, splits the document into overlapping pieces for embedding.
**Embeddings** — `sentence-transformers/all-MiniLM-L6-v2` (HuggingFace), runs locally on CPU, no API cost.
**Vector store** — FAISS, local similarity search over the embedded chunks.
**Retrieval-grounded answers** — for both Summarize and Ask Questions features, relevant chunks are retrieved and passed as context to the LLM, rather than answering from the model's general knowledge.

---

## AI Provider

**Groq API** — used for all document-related AI calls (Summarize, Q&A, Quiz generation). Chosen for its generous free tier compared to Gemini, after running into rate-limit issues on earlier weeks' projects.

---

## Structured Output (reused pattern from Week 3)

**Quiz generation** — the only feature in this app producing structured JSON rather than plain text, because the output needs to drive an interactive UI (question/options/correct-answer), not just be read as prose.

Schema:
```json
{
  "questions": [
    { "question": "string", "options": ["string", "string", "string", "string"], "answer": "string" }
  ]
}
```

The parsed JSON is rendered into radio-button/card UI elements — the raw JSON itself is never shown to the student.

---

## Timetable Storage — Google Sheets (backend, hidden from the student)

**gspread (Python library)** — used from within the Streamlit app to read/write the Google Sheet directly, without the student ever seeing a Sheets link or interface.

**Google Service Account** — a non-human Google account (its own email + a JSON credentials file) used for server-side Sheets access. The target Sheet is shared with this Service Account's email (Editor access) once, during setup — this is how Streamlit authenticates without any login popup for the student.

**Email as primary key** — each student's timetable is one row, matched/updated by their email, so resubmitting the form updates their existing row instead of creating duplicates (same pattern as `Serial No` matching in the Week 5 project, but keyed on email here since each student only ever has one timetable).

**Access model** — the Sheet itself is never shared with or exposed to students; only the developer/admin's accounts (Streamlit's Service Account, and separately the n8n connection) can see it. Students only ever interact through the Streamlit form — identical in spirit to how the Week 5 Google Form was the only student-facing surface, with the Sheet and n8n workflow entirely backend.

---

## Automation — n8n (Week 5 pattern reused, no AI step needed here)

**Schedule Trigger** — runs the workflow on a fixed interval (~every 5 minutes) rather than reacting to an event, since this workflow needs to proactively check "is it time yet?" rather than respond to something happening.

**Time-window comparison logic** — for each row, current time is compared against the row's scheduled time across three windows (before / at start / late-after), rather than an exact-match, since the workflow only runs every few minutes and could miss an exact-second match.

**Status-gated sending** — a row's session is skipped if its `Status` column already shows `In Progress`/`Done`, giving the student a way to silence further notifications by confirming they're on it.

**Sent-flag tracking** — a column tracks which notification stages have already fired for a given session, preventing the same reminder from being sent repeatedly across multiple 5-minute polling cycles.

**No AI call in this workflow** — unlike Week 5's categorize-and-reply step, this workflow's emails are templated (subject/time/status slotted into a fixed HTML layout), since the message content doesn't need to vary by meaning — only the data inside it changes.

**Gmail node (OAuth)** — same pattern as Week 5, sends the actual notification email, addressed to each row's own email address.

---

## Live In-App Timer (new concept for this project)

**Client-side countdown vs. backend notification** — two separate systems solving the same underlying problem (telling the student about session timing) through different channels:
- The **n8n + email** path reaches the student even when the app/tab is closed
- The **in-app timer + color banner** path only works while the student is actively viewing the app, but updates live and doesn't require an email round-trip

**Color-state logic** — purely a function of time-remaining relative to the scheduled time (green >5min before, blue within 5min before/at start, red >5min after) — deliberately independent of the `Status` column, since the timer reflects the clock, while notifications (both in-app and email) are what respect the `Status` "silence" behavior.

---

## Credentials Needed
- Groq API key (document AI features)
- Google Service Account JSON (Sheets read/write from Streamlit)
- Google account (Sheets access, OAuth via n8n)
- Gmail account (OAuth via n8n) for notification sending
