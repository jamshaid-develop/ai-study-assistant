# 📚 AI Study Assistant

A full-stack mini app built with **Streamlit** that turns one uploaded document into a complete study toolkit — summary, Q&A chat, an auto-generated quiz — plus a live study timetable with color-coded reminders. Built as the Week 6 Capstone for **Neurofive Solutions'** Generative AI & Prompt Engineering program.

Originally inspired by a solo hackathon submission ("AI Study Assistant" — summarize notes, answer questions, generate quizzes, personalized study plans), rebuilt end-to-end here with a real, working notification/timer layer added.

---

## 🎯 The Problem

Students collect notes but rarely revisit them effectively — summarizing takes time, self-testing requires manually writing questions, and study schedules get forgotten without something actively reminding them when a session is due (or overdue).

This app solves all three around a **single uploaded document**: read it once, then summarize it, ask it questions, quiz yourself on it, and separately, keep a live study timetable that visually (and audibly) tells you when a session is starting or you're falling behind — without needing a login system.

---

## ✨ What It Does

### 📄 Document Tools
- **Upload** a PDF, DOCX, or TXT file (your notes)
- **Summarize** — one click, plain-English summary of the whole document, downloadable as `.txt`
- **Ask Questions** — chat with your notes; answers are grounded in the actual document content (RAG), not the model's general knowledge
- **Quiz** — auto-generates multiple-choice questions from your notes, with instant scoring

### 🗓️ Study Planner
- No login — enter your email, and your existing timetable (if any) loads automatically; if none exists, you start a fresh one
- Add subjects with a time slot each (e.g. `9:00 PM - 10:00 PM`)
- **Live countdown timer** per session, color-coded:
  - 🟢 **Green** — more than 5 minutes until start (or already past today, showing tomorrow's countdown)
  - 🔵 **Blue** — within 5 minutes of start, through the first few minutes after
  - 🔴 **Red** — more than 5 minutes late and not yet marked started
- **In-app notification banners + a browser beep alarm** at three moments: before, at start, and if late
- **"✅ Started"** button — silences alerts for that session and marks it acknowledged
- Once a session's scheduled **end time** passes, its status automatically resets to `Pending` and the badge returns to a fresh countdown for its next occurrence — nothing stays stuck as "late" or "in progress" into the next day
- A **🔄 Refresh** button forces an immediate re-sync with the stored timetable (Google Sheets has a brief read-after-write delay, so this guarantees you're seeing the latest state)

---

## 🧠 How It Works (Architecture)

```
Document Tools (session-only, resets per upload)
─────────────────────────────────────────────────
Upload → chunk (LangChain) → embed (HuggingFace, local)
      → FAISS vector index
      → Summarize / Ask Questions / Quiz → Groq LLM


Study Planner (persistent, multi-user)
─────────────────────────────────────────────────
Student enters email
      → Streamlit (via a Google Service Account) looks up
        matching rows in a Google Sheet
      → Found  → existing timetable displayed
      → Not found → empty form to create one
Add/Edit/Delete subject → written back to the Sheet
      (Email + Subject = the matching key; no duplicates)

Live timer (client-side, while the tab is open)
      → recomputed fresh every 30s (st_autorefresh)
      → color + banner + one-time beep per notification phase
      → purely time-based logic; Status only silences alerts,
        it doesn't freeze the badge once the session's window ends
```

**Why no login system:** the Study Planner uses an **email-lookup pattern** instead of authentication — since Streamlit holds no memory between browser sessions, the student's email itself is the key used to find (or create) their record in the Sheet, the same way a unique key works in any CRUD system.

**Why RAG instead of dumping the whole document into every prompt:** for the Q&A and Quiz features, only the most relevant chunks of the document are retrieved and passed to the model — keeping responses grounded and efficient rather than re-sending the entire document on every question.

---

## 🛠️ Tech Stack

| Component | Tool |
|---|---|
| Frontend/App | Streamlit |
| Document AI (Summarize, Q&A, Quiz) | Groq API (`llama-3.3-70b-versatile`) |
| Embeddings | HuggingFace `all-MiniLM-L6-v2` (local, free, no API cost) |
| Vector store / Retrieval | FAISS |
| Structured output | Quiz generation — enforced JSON schema, parsed into an interactive UI |
| Timetable storage | Google Sheets (via `gspread` + a Service Account, no student-facing login) |
| Live updates | `streamlit-autorefresh` |
| In-app alerts | Browser-native beep via the Web Audio API (no audio file needed) |

**Advanced elements covered (task required at least one — this app includes three):**
- ✅ RAG (document upload + retrieval-grounded answers)
- ✅ Structured JSON output (Quiz generation)
- ✅ Automation-adjacent live logic (timer state machine + auto status reset)

---

## ⚙️ Setup

### 1. Clone and enter the project
```bash
git clone <your-repo-url>
cd ai-study-assistant
```

### 2. Create a virtual environment (Python 3.12)
```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
source .venv/bin/activate   # macOS/Linux
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure API key
Copy `.env.example` to `.env` and add your Groq API key (free tier at [console.groq.com](https://console.groq.com)):
```
GROQ_API_KEY=your_groq_api_key_here
```

### 5. Set up Google Sheets access (for the Study Planner)
1. Create a Google Cloud project → enable **Google Sheets API** and **Google Drive API**
2. Create a **Service Account** → generate a JSON key → save it as `service_account.json` in the project root
3. Create a Google Sheet named `StudyPlannerData` with header row: `Email | Name | Subject | Time | Status`
4. Share that Sheet with the Service Account's email (found in the JSON as `client_email`), Editor access
5. Confirm `.env` has:
   ```
   GOOGLE_SERVICE_ACCOUNT_FILE=service_account.json
   STUDY_PLANNER_SHEET_NAME=StudyPlannerData
   ```

### 6. Run the app
```bash
streamlit run app.py
```

[live demo]( https://ai-study-assistant-hmgraax38smpkqegn6fvsb.streamlit.app/)



---

## 📁 Project Structure

```
ai-study-assistant/
│
├── app.py               # Main Streamlit app — navigation, UI, orchestration
├── rag_utils.py           # Document load/chunk/embed/retrieve helpers
├── ai_utils.py              # Groq-powered Summarize / Q&A / Quiz functions
├── sheet_utils.py             # Google Sheets CRUD (email-based lookup, order/extra-column safe)
├── timer_utils.py                # Live session state machine + color logic + beep alert
│
├── requirements.txt                 # Dependencies
├── .env.example                       # API key / credentials placeholders
├── .env                                  # Your real keys (never committed)
├── service_account.json                    # Your real Google credentials (never committed)
├── .gitignore
│
├── PRD.md                                    # Full requirements & architecture doc
├── SKILLS.md                                   # Tools/concepts reference
└── README.md                                     # This file
```

---

## 🧪 Testing Notes

Tested end-to-end with multiple realistic documents (study notes across different subjects) for Summarize/Q&A/Quiz, and with multiple student emails for the Study Planner to confirm:
- Each student only ever sees their own timetable
- Re-submitting the same email updates the existing record rather than duplicating it
- Color/notification state is always computed live, never stale — verified across session start, mid-session, late, and post-end-time scenarios
- Quiz JSON output was validated against the expected schema across several generated quizzes

---

## 🚧 What I'd Improve With More Time

- **Persistent document library** — currently the uploaded document only lasts for the browser session; a logged-in student re-opening the app has to re-upload. A lightweight per-user document store (keyed the same way as the timetable) would fix this.
- **Real automation for reminders** — the current live timer only works while the tab is open. An earlier version of this project used n8n + Gmail to send actual email reminders even when the app was closed; this was descoped due to the automation platform's trial expiring, but is a natural next step (see PRD.md for the originally designed flow).
- **Multi-document support** — currently scoped to one document per session by design; a real product would let students manage a small library of notes.
- **Better time-slot input** — the Study Planner currently takes a free-text time field; a proper time picker widget would reduce input errors.
- **Deployment** — currently intended for local/Streamlit Cloud use; a production version would need proper secrets management for the Service Account credentials.

---

## ⚠️ Disclaimer

This is an educational capstone project demonstrating full-stack AI application concepts (prompt engineering, API integration, RAG, structured outputs, and live client-side state management). Not intended for production use as-is.
