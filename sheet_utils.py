"""
sheet_utils.py — Google Sheets read/write helpers for the Study Planner.

Design (per PRD Section 3.7a): row-per-subject, matched on (Email, Subject).
No login system — the student looks up their own data by entering their
email; if no record exists, they're treated as new and can create one.

Required columns (any order, extra columns are fine and ignored):
  Email | Name | Subject | Time | Status
"""

import os
import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADERS = ["Email", "Name", "Subject", "Time", "Status"]
STATUS_PENDING = "Pending"
STATUS_STARTED = "In Progress"


def get_worksheet():
    """
    Authenticates with the Service Account and returns the first worksheet
    of the configured Sheet. Works both locally (service_account.json file)
    and on Streamlit Cloud (st.secrets["gcp_service_account"]).
    """
    sheet_name = os.environ.get("STUDY_PLANNER_SHEET_NAME", "StudyPlannerData")

    try:
        import streamlit as st
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        else:
            raise KeyError
    except Exception:
        creds_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
        if not os.path.exists(creds_path):
            raise FileNotFoundError(
                f"Service account file not found at '{creds_path}', and no "
                "st.secrets['gcp_service_account'] configured either. "
                "See README.md for setup steps."
            )
        creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)

    client = gspread.authorize(creds)

    sheet = client.open(sheet_name).sheet1

    # Ensure the required columns exist — extra columns (e.g. old notification
    # tracking fields) are fine and ignored, order doesn't matter either.
    existing_headers = sheet.row_values(1)
    if not existing_headers:
        sheet.append_row(HEADERS)
    else:
        missing = [h for h in HEADERS if h not in existing_headers]
        if missing:
            raise ValueError(
                f"Sheet is missing required column(s): {missing}. "
                f"Row 1 must include at least: {HEADERS} (extra columns and any order are fine). "
                f"Currently found: {existing_headers}"
            )

    return sheet


def _col_index(sheet, header_name: str) -> int:
    """Returns the 1-indexed column number for a given header name (order-agnostic)."""
    headers = sheet.row_values(1)
    return headers.index(header_name) + 1


def get_timetable_by_email(email: str) -> list[dict]:
    """
    Returns all rows (as dicts) matching this email, i.e. all of this
    student's subjects/sessions. Returns an empty list if none found.
    """
    sheet = get_worksheet()
    records = sheet.get_all_records()
    email = email.strip().lower()

    return [
        {
            "Email": r.get("Email", ""),
            "Name": r.get("Name", ""),
            "Subject": r.get("Subject", ""),
            "Time": r.get("Time", ""),
            "Status": r.get("Status", STATUS_PENDING),
            "_row_number": i + 2,  # +2: header row + 1-indexing
        }
        for i, r in enumerate(records)
        if str(r.get("Email", "")).strip().lower() == email
    ]


def save_subject(email: str, name: str, subject: str, time_slot: str) -> None:
    """
    Adds a new row for (email, subject). Does not check for existing
    (email, subject) duplicates here — call update_subject() instead if
    the row already exists and should be edited.

    Writes by column name (not fixed positions), so it's safe even if the
    sheet has extra columns or a different column order.
    """
    sheet = get_worksheet()
    headers = sheet.row_values(1)

    new_row = [""] * len(headers)
    values = {"Email": email.strip().lower(), "Name": name, "Subject": subject,
              "Time": time_slot, "Status": STATUS_PENDING}
    for key, value in values.items():
        new_row[headers.index(key)] = value

    sheet.append_row(new_row)


def update_subject(row_number: int, name: str, time_slot: str, status: str | None = None) -> None:
    """
    Updates an existing row (by its sheet row number) — used when the
    student edits a subject's time, or when their name changes.
    """
    sheet = get_worksheet()
    sheet.update_cell(row_number, _col_index(sheet, "Name"), name)
    sheet.update_cell(row_number, _col_index(sheet, "Time"), time_slot)
    if status is not None:
        sheet.update_cell(row_number, _col_index(sheet, "Status"), status)


def mark_started(row_number: int) -> None:
    """Marks a single session's Status as 'In Progress' (student confirms they're on it)."""
    sheet = get_worksheet()
    sheet.update_cell(row_number, _col_index(sheet, "Status"), STATUS_STARTED)


def reset_status_to_pending(row_number: int) -> None:
    """
    Resets a session's Status back to 'Pending' — called once a session's
    end time has passed, so nothing stays stale as 'In Progress' (or 'late')
    into the next day's occurrence of that subject.
    """
    sheet = get_worksheet()
    sheet.update_cell(row_number, _col_index(sheet, "Status"), STATUS_PENDING)


def delete_subject(row_number: int) -> None:
    """Removes a single subject/session row entirely."""
    sheet = get_worksheet()
    sheet.delete_rows(row_number)