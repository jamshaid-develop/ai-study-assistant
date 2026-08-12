"""
AI Study Assistant — Capstone (Week 6)

Full app — all steps integrated:
  - Step 1: base app structure (sidebar navigation, page config)
  - Step 2: Document upload + RAG index building
  - Step 3: Summarize / Ask Questions / Quiz Generator (Groq)
  - Step 4: Study Planner (email lookup + Google Sheets CRUD)
  - Step 5: Live timer + color states + in-app notification banners
"""

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from streamlit_autorefresh import st_autorefresh

from rag_utils import load_document, build_vectorstore, get_full_text, retrieve_context
from ai_utils import summarize_document, answer_question, generate_quiz
from sheet_utils import (
    get_timetable_by_email, save_subject, mark_started, delete_subject,
    reset_status_to_pending, STATUS_STARTED,
)
from timer_utils import get_session_state, color_badge_html, alert_sound_html

load_dotenv()

st.set_page_config(
    page_title="AI Study Assistant",
    page_icon="📚",
    layout="wide",
)

# ---------------- Sidebar: navigation ----------------
with st.sidebar:
    st.title("📚 AI Study Assistant")
    st.caption("Summarize, ask questions, quiz yourself, and stay on schedule — all from one document.")

    st.divider()
    page = st.radio(
        "Go to",
        ["📄 Document Tools", "🗓️ Study Planner"],
        label_visibility="collapsed",
    )

    st.divider()
    st.markdown(
        "**How it works:**\n"
        "1. Upload your notes (PDF/DOCX/TXT)\n"
        "2. Summarize, ask questions, or generate a quiz\n"
        "3. Set up your study timetable and get live reminders"
    )


# ---------------- Session state defaults ----------------
defaults = {
    "documents": None,
    "vectorstore": None,
    "doc_name": None,
    "chunk_count": 0,
    "chat_history": [],
    "summary_text": None,
    "quiz_data": None,
    "quiz_submitted": False,
    "planner_email": None,
    "planner_name": "",
    "planner_rows": [],
    "sounded_stages": set(),
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ==================================================================
# PAGE: Document Tools
# ==================================================================
if page == "📄 Document Tools":
    st.title("📄 Document Tools")
    st.caption("Upload your notes once, then summarize, ask questions, or generate a quiz from them.")

    with st.expander("📤 Upload your document", expanded=(st.session_state.vectorstore is None)):
        st.markdown(
            "**Supported formats:** PDF, DOCX, TXT\n\n"
            "**Max file size:** 15 MB\n\n"
            "Tip: a few pages of notes works best for quick indexing."
        )
        uploaded_file = st.file_uploader(
            "Choose a file",
            type=["pdf", "docx", "txt"],
            label_visibility="collapsed",
        )

        if uploaded_file is not None and uploaded_file.name != st.session_state.doc_name:
            with st.spinner("Reading and indexing your document..."):
                try:
                    documents = load_document(uploaded_file)
                    vectorstore, chunk_count = build_vectorstore(documents)

                    st.session_state.documents = documents
                    st.session_state.vectorstore = vectorstore
                    st.session_state.doc_name = uploaded_file.name
                    st.session_state.chunk_count = chunk_count
                    # Reset previous document's results so nothing carries over
                    st.session_state.chat_history = []
                    st.session_state.summary_text = None
                    st.session_state.quiz_data = None
                    st.session_state.quiz_submitted = False

                    st.success(f"Indexed **{uploaded_file.name}** into {chunk_count} chunks. Ready to use below.")
                except ValueError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"Something went wrong processing this file: {e}")

    if st.session_state.vectorstore is None:
        st.info("👆 Upload a document to unlock Summarize, Q&A, and Quiz below.")
    else:
        st.success(f"Currently loaded: **{st.session_state.doc_name}**")

        tab_summary, tab_qa, tab_quiz = st.tabs(["📝 Summarize", "💬 Ask Questions", "🧠 Quiz"])

        # ---------------- Summarize ----------------
        with tab_summary:
            if st.button("Generate Summary", type="primary"):
                with st.spinner("Reading through your document..."):
                    try:
                        full_text = get_full_text(st.session_state.documents)
                        st.session_state.summary_text = summarize_document(full_text)
                    except Exception as e:
                        st.error(f"Couldn't generate a summary: {e}")

            if st.session_state.summary_text:
                st.markdown(st.session_state.summary_text)
                st.download_button(
                    "⬇️ Download summary as .txt",
                    data=st.session_state.summary_text,
                    file_name=f"summary_{st.session_state.doc_name or 'document'}.txt",
                    mime="text/plain",
                )

        # ---------------- Q&A ----------------
        with tab_qa:
            for role, msg in st.session_state.chat_history:
                with st.chat_message(role):
                    st.markdown(msg)

            question = st.chat_input("Ask a question about your notes...")
            if question:
                st.session_state.chat_history.append(("user", question))
                with st.chat_message("user"):
                    st.markdown(question)

                with st.chat_message("assistant"):
                    with st.spinner("Thinking..."):
                        try:
                            context = retrieve_context(st.session_state.vectorstore, question)
                            answer = answer_question(context, question)
                            st.markdown(answer)
                            st.session_state.chat_history.append(("assistant", answer))
                        except Exception as e:
                            st.error(f"Couldn't answer that: {e}")

        # ---------------- Quiz ----------------
        with tab_quiz:
            num_q = st.slider("Number of questions", min_value=3, max_value=10, value=5)

            if st.button("Generate Quiz", type="primary"):
                with st.spinner("Building your quiz..."):
                    try:
                        full_text = get_full_text(st.session_state.documents)
                        st.session_state.quiz_data = generate_quiz(full_text, num_questions=num_q)
                        st.session_state.quiz_submitted = False
                    except Exception as e:
                        st.error(f"Couldn't generate a quiz: {e}")

            if st.session_state.quiz_data:
                with st.form("quiz_form"):
                    user_answers = []
                    for i, q in enumerate(st.session_state.quiz_data):
                        st.markdown(f"**{i + 1}. {q['question']}**")
                        choice = st.radio(
                            f"q_{i}", q["options"], key=f"quiz_q_{i}",
                            label_visibility="collapsed",
                        )
                        user_answers.append(choice)

                    submitted = st.form_submit_button("Submit Quiz")

                if submitted:
                    st.session_state.quiz_submitted = True

                if st.session_state.quiz_submitted:
                    score = 0
                    st.divider()
                    for i, q in enumerate(st.session_state.quiz_data):
                        correct = q["answer"]
                        chosen = user_answers[i]
                        is_correct = chosen.strip().lower() == correct.strip().lower()
                        score += int(is_correct)
                        icon = "✅" if is_correct else "❌"
                        st.markdown(f"{icon} **Q{i + 1}:** {q['question']}")
                        if not is_correct:
                            st.caption(f"Your answer: {chosen} — Correct answer: {correct}")

                    st.success(f"Score: {score} / {len(st.session_state.quiz_data)}")


# ==================================================================
# PAGE: Study Planner
# ==================================================================
elif page == "🗓️ Study Planner":
    st.title("🗓️ Study Planner")
    st.caption("Set your study timetable and get reminders before, at, and after each session.")

    # ---- Email lookup (no login system — session recovery pattern, PRD 3.7a) ----
    if st.session_state.planner_email is None:
        st.info("Enter your email to load your existing timetable, or start a new one.")
        with st.form("email_lookup"):
            email_input = st.text_input("Your email")
            submitted = st.form_submit_button("Continue")

        if submitted and email_input.strip():
            try:
                rows = get_timetable_by_email(email_input)
                st.session_state.planner_email = email_input.strip().lower()
                st.session_state.planner_rows = rows
                st.session_state.planner_name = rows[0]["Name"] if rows else ""
                st.rerun()
            except FileNotFoundError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"Couldn't reach the timetable storage: {e}")

    # ---- Timetable view (existing or new student) ----
    else:
        email = st.session_state.planner_email
        rows = st.session_state.planner_rows

        # Live refresh every 30s so the timer/colors update while the tab is open (PRD 3.8)
        st_autorefresh(interval=30_000, key="planner_autorefresh")

        col_a, col_b = st.columns([4, 1])
        with col_a:
            today_str = __import__('datetime').datetime.now().strftime('%A, %d %B %Y')
            if rows:
                st.success(f"Hi **{st.session_state.planner_name}** — here's your study plan.  \n📅 {today_str}")
            else:
                st.info(f"No timetable found for **{email}** yet — add your first subject below.  \n📅 {today_str}")
        with col_b:
            rb1, rb2 = st.columns(2)
            if rb1.button("🔄 Refresh"):
                st.session_state.planner_rows = get_timetable_by_email(email)
                st.rerun()
            if rb2.button("🔓 Switch"):
                st.session_state.planner_email = None
                st.session_state.planner_rows = []
                st.rerun()
            st.caption(f"⏱ {__import__('datetime').datetime.now().strftime('%I:%M %p')}")

        # ---- Auto-reset: once a session's end time has passed, its Status snaps back
        #      to Pending in the Sheet — so nothing stays stale as "In Progress"/"late"
        #      into the next day's occurrence (PRD 3.7b). Runs once per row per app load
        #      /refresh; harmless to call again if already Pending. ----
        for row in rows:
            state = get_session_state(row["Time"], status=row["Status"])
            if state["ended"] and row["Status"] != "Pending":
                reset_status_to_pending(row["_row_number"])
                row["Status"] = "Pending"

        # ---- In-app notification banners (before / start / late) — separate from any
        #      external notification channel; only visible while the app is open.
        #      Each distinct phase gets its own alarm — "before" firing doesn't block
        #      "starting now" or "late" from firing later, since each has its own key. ----
        for row in rows:
            state = get_session_state(row["Time"], status=row["Status"])
            stage_key = f"{row['_row_number']}_{state['phase']}"

            if state["phase"] == "upcoming_close":
                st.warning(f"🔔 **{row['Subject']}** — {state['label']}")
                if stage_key not in st.session_state.sounded_stages:
                    components.html(alert_sound_html(35), height=0)
                    st.session_state.sounded_stages.add(stage_key)
            elif state["phase"] == "active_grace":
                st.info(f"▶️ **{row['Subject']}** — {state['label']}")
                if stage_key not in st.session_state.sounded_stages:
                    components.html(alert_sound_html(35), height=0)
                    st.session_state.sounded_stages.add(stage_key)
            elif state["phase"] == "active_late":
                st.error(f"⏰ You're **{state['label']}** for **{row['Subject']}**!")
                if stage_key not in st.session_state.sounded_stages:
                    components.html(alert_sound_html(35), height=0)
                    st.session_state.sounded_stages.add(stage_key)

        if rows:
            st.markdown("#### Your sessions")
            for row in rows:
                state = get_session_state(row["Time"], status=row["Status"])

                c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 2, 2])
                c1.markdown(f"**{row['Subject']}**")
                c2.markdown(row["Time"])
                c3.markdown(f"Status: `{row['Status']}`")
                c4.markdown(color_badge_html(state["color"], state["label"]), unsafe_allow_html=True)
                with c5:
                    bc1, bc2 = st.columns(2)
                    if row["Status"] != STATUS_STARTED:
                        if bc1.button("✅ Started", key=f"start_{row['_row_number']}"):
                            mark_started(row["_row_number"])
                            st.session_state.planner_rows = get_timetable_by_email(email)
                            st.rerun()
                    if bc2.button("🗑️", key=f"del_{row['_row_number']}"):
                        delete_subject(row["_row_number"])
                        st.session_state.planner_rows = get_timetable_by_email(email)
                        st.rerun()
            st.divider()

        st.markdown("#### Add a subject")
        with st.form("add_subject", clear_on_submit=True):
            name_input = st.text_input("Your name", value=st.session_state.planner_name)
            subj_col, time_col = st.columns(2)
            subject_input = subj_col.text_input("Subject")
            time_input = time_col.text_input("Time slot (e.g. 9:00 PM - 10:00 PM)")

            add_submitted = st.form_submit_button("➕ Add to timetable", type="primary")

        if add_submitted:
            if not (name_input.strip() and subject_input.strip() and time_input.strip()):
                st.warning("Please fill in your name, subject, and time slot.")
            else:
                try:
                    save_subject(email, name_input.strip(), subject_input.strip(), time_input.strip())
                    st.session_state.planner_name = name_input.strip()
                    st.session_state.planner_rows = get_timetable_by_email(email)
                    st.rerun()
                except Exception as e:
                    st.error(f"Couldn't save this subject: {e}")