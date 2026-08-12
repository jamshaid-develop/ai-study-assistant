# PRD — AI Study Assistant (Capstone)

**Project:** Week 6 — Generative AI & Prompt Engineering Capstone (Neurofive Solutions)
**Type:** Full-stack mini app (Streamlit) + automation add-on (n8n)
**Status:** Planning

---

## 1. Objective

Build a single, focused AI-powered web app centered on **one document a student uploads** — their own notes — that helps them summarize, ask questions, and self-test on that material, plus a practical **study timetable with automated reminder/late notifications**.

Origin: extends an idea from a solo hackathon submission ("AI Study Assistant" — summarize notes, answer questions, generate quizzes, personalized study plans), now built end-to-end for this capstone with a real notification layer added.

Scope is deliberately kept tight — everything revolves around one uploaded document plus one timetable, no unrelated features.

---

## 2. Core Flow

```
Student opens the Streamlit app
        ↓
Uploads a document (PDF/DOCX/TXT) — their notes
        ↓
    ┌───────────────┬──────────────┬─────────────────┐
    ↓               ↓              ↓                  
Summarize        Ask Questions   Generate Quiz    
(plain text)     (RAG chat)      (structured JSON  
                                  → interactive UI)
        ↓ (separate, independent feature)
Student fills in name + email + timetable (subject + time slots)
        ↓
Saved/updated in a Google Sheet (email = unique key; re-submitting updates their row, doesn't duplicate)
        ↓
[n8n, running independently, every ~5 minutes]
Reads all rows → compares current time to each student's scheduled times
        ↓
Sends the matching student a reminder/start/late email via the connected Gmail account,
UNLESS their Status is already "In Progress"/"Done" for that session
```

---

## 3. Features

### 3.1 Document Upload
- Accepts PDF, DOCX, TXT (reused pattern from Week 1-2 RAG project)
- Builds a local embeddings index (HuggingFace + FAISS) for that session

### 3.2 Summarize
- One-click button → AI (Groq) generates a plain-text summary of the uploaded document
- Output format: plain prose, no JSON — matches how a person would summarize it

### 3.3 Ask Questions (Chat with your notes)
- RAG-based Q&A — student asks anything about the uploaded document, answer is grounded in retrieved chunks
- Plain-text conversational answers

### 3.4 Quiz Generator
- AI (Groq) generates quiz questions from the document content
- **Structured JSON output** (question, options, correct answer) — this is the app's structured-output element from Week 3
- Rendered as an interactive quiz UI (radio buttons/cards), not raw JSON shown to the user

### 3.5 Study Planner + Notifications (the automation element from Week 5)
- Student fills a form: Name, Email, list of (Subject, Scheduled Time) entries
- Saved to a Google Sheet — **email is the unique/primary key**; resubmitting updates the same row rather than creating a duplicate
- Student can mark a session **"Mark as Started"** in the app at any time — this updates their row's `Status` column
- n8n (separate, scheduled workflow, not tied to the Streamlit session):
  - Runs on a timer (~every 5 minutes)
  - For every row/session, compares current time against the scheduled time in three windows:
    - **~10 min before** → reminder email ("upcoming soon")
    - **At start time** → "session starting now" email
    - **~5 min after, if still Pending** → "you're running late" email
  - Skips sending if that session's `Status` is already `In Progress` or `Done`
  - Tracks which notifications were already sent (a flag/column) so the same reminder isn't sent twice
  - Sends via the connected Gmail account, addressed to that row's own email — each student only ever receives their own notifications

### 3.6 No AI in the notification workflow
- The n8n workflow does pure time-comparison logic — no AI call needed for this piece, since messages are templated (subject/time/status inserted into a fixed HTML format), not generated

### 3.7 Access Model (backend hidden from the student)
- Same pattern as the Week 5 project: the student only ever interacts with the Streamlit form
- Google Sheet and n8n workflow are backend infrastructure, connected via the developer/admin's own accounts — never exposed to or accessible by the student
- The Streamlit app shows each visitor **only their own timetable**, filtered by their own email — no visibility into other students' data

### 3.7a Session Recovery (no login system — email lookup instead)
Streamlit holds no memory between browser sessions (closing the tab loses all local state). Since Study Planner data must persist and be retrievable later (unlike the Upload/Summarize/Q&A/Quiz features, which are correctly session-only per document), the app uses an **email-lookup pattern** instead of building a full login system:

- On opening the Study Planner section, the student first enters their email
- App queries the Google Sheet for a matching row/record
  - **Match found** → their existing timetable is fetched and displayed
  - **No match** → treated as a new student, empty form shown to create one
- This is the same key-based CRUD logic already used for saving/updating (email as unique key) — just applied to reads as well, so no separate authentication system is needed for this app's scope

### 3.7b Daily Color Reset
The timer's color state (Section 3.8) is derived fresh from the *current* date/time every time the app is opened or refreshed — it is never stored. This means:
- A session whose scheduled time has passed shows **red** for up to a defined window (e.g. 1 hour) after its scheduled time if never marked as started/done
- Once that window passes (or on a new day), re-opening the app shows the color recalculated against the current time — a session from yesterday does not show as perpetually "red"
- Only the underlying schedule (subject + time) and `Status` are persisted in the Sheet; color is always a live computation, not a stored value

### 3.8 Live In-App Timer + Notification Highlights
While the student has the app open, the timetable view includes a live countdown clock per session (updates continuously while the tab is open, similar in spirit to a digital countdown display):

- **Color states**, driven purely by time-to-session (not by Status):
  - **Green** — more than 5 minutes remaining before start
  - **Blue** — within the last 5 minutes before start, through the scheduled start time itself
  - **Red** — more than 5 minutes past the scheduled start time (running late)
- **In-app notification banners** (separate from, and in addition to, the email notifications sent by n8n) surface at the same three moments:
  - Before (~5-10 min out)
  - At start
  - Late (if Status hasn't been changed)
- This is purely a front-end/live-session feature — it only reflects reality while the student is actively viewing the app; the email notifications from n8n remain the channel that reaches them when the app/tab is closed
- No new advanced technique introduced here — it's a UI/state layer on top of the same timetable data already being displayed

---

## 4. Multi-user Support

- The Streamlit app link can be shared with any number of users (like the Week 5 Google Form)
- Each visitor who fills the timetable form gets their own row in the Sheet, identified by their own email
- n8n checks **all rows every cycle** and emails each student individually — no cross-contamination between users, no single user needing to be "the" account (the Gmail account is only the sender, not tied to any one student)

---

## 5. Email Notification Format

Following the same branded HTML pattern used in the Week 5 project:
- Top: App name/title header (NeuroFive-style branding)
- Below: Student's name + email
- Below: The alert itself — one of:
  - "Your **[Subject]** session starts in **[X] minutes**"
  - "Your **[Subject]** session is starting now"
  - "You're **[X] minutes** late for your **[Subject]** session"
- Footer: reference line noting this was generated by the AI Study Assistant app (developer attribution)

---

## 6. Tech Stack

| Component | Tool |
|---|---|
| Frontend/App | Streamlit |
| Document AI (Summarize, Q&A, Quiz) | Groq API |
| Embeddings/Retrieval | HuggingFace (all-MiniLM-L6-v2) + FAISS |
| Timetable storage | Google Sheets (via `gspread` + Service Account) |
| Notification automation | n8n (Schedule Trigger, no AI step) |
| Email delivery | Gmail (OAuth, connected in n8n) |

---

## 7. Advanced Elements Covered (task requirement: at least one)

- ✅ **RAG** (document upload + retrieval-grounded Q&A/summarize/quiz)
- ✅ **Structured JSON output** (Quiz generation)
- ✅ **Automation trigger** (n8n scheduled notification checker)

All three are included — exceeds the "at least one" requirement, each serving a distinct, non-redundant purpose.

---

## 8. Success Criteria

- [ ] Student can upload a document and get a correct summary
- [ ] Student can ask at least 3-5 realistic questions and get grounded answers
- [ ] Quiz generates valid, document-grounded questions in a working interactive format
- [ ] Student can submit a timetable, and resubmitting updates (not duplicates) their row
- [ ] "Mark as Started" correctly suppresses further notifications for that session
- [ ] All three notification types (before/start/late) fire correctly and go only to the right student's email
- [ ] Tested end-to-end with 2+ different student accounts to confirm multi-user isolation
- [ ] Each student sees only their own timetable — no access to the Sheet or n8n backend
- [ ] Live timer shows correct color state (green/blue/red) matching time-to-session, and updates while the app is open
- [ ] In-app notification banners appear at the same before/start/late moments as the email notifications
- [ ] App tested with 3-5 realistic documents/inputs, rough edges fixed

---

## 9. Out of Scope
- True OS-level push notifications (not possible from a web app — email is the notification channel instead)
- AI-generated notification message content (templated, not AI-generated — no need, no added value)
- Multi-document support (one document per session, matches hackathon-scale scope)

---

## 10. Deliverables
- Working Streamlit app (public GitHub repo)
- n8n workflow (exported JSON, included in repo)
- `SKILLS.md` — tools/concepts reference
- `README.md` — problem, approach, tech stack, what to improve with more time
- 3-5 min demo video (end-to-end product walkthrough), posted to LinkedIn tagging Neurofive Solutions
