"""Seed sample data for a given user.

Usage:
    python seed.py user@example.com

Looks up the user by email (via service-role client), then inserts demo classes,
schedule entries, assignments, notes, and study sessions. Safe to re-run — but
it will stack duplicates, so only run once per account.
"""
import sys
from datetime import date, timedelta

from supabase_client import get_admin_client


def main(email: str) -> None:
    admin = get_admin_client()

    # Find the user — the admin API is the easiest way without a JWT.
    users = admin.auth.admin.list_users()
    user = next((u for u in users if u.email == email), None)
    if not user:
        print(f"No user with email {email}. Sign up first, then seed.")
        sys.exit(1)
    uid = user.id

    # Classes
    classes = [
        {"user_id": uid, "name": "Intro to Psychology", "professor": "Dr. Park",  "location": "Hall A 201", "color": "#FADADD"},
        {"user_id": uid, "name": "Linear Algebra",      "professor": "Prof. Kim", "location": "Science 105","color": "#F8C8DC"},
        {"user_id": uid, "name": "Creative Writing",    "professor": "Ms. Lee",   "location": "Arts 12",    "color": "#E79FB3"},
    ]
    cls_rows = admin.table("classes").insert(classes).execute().data

    # Schedule (Mon=0)
    schedule = [
        {"class_id": cls_rows[0]["id"], "day_of_week": 0, "start_time": "09:00", "end_time": "10:30"},
        {"class_id": cls_rows[0]["id"], "day_of_week": 2, "start_time": "09:00", "end_time": "10:30"},
        {"class_id": cls_rows[1]["id"], "day_of_week": 1, "start_time": "11:00", "end_time": "12:30"},
        {"class_id": cls_rows[1]["id"], "day_of_week": 3, "start_time": "11:00", "end_time": "12:30"},
        {"class_id": cls_rows[2]["id"], "day_of_week": 4, "start_time": "14:00", "end_time": "15:30"},
    ]
    admin.table("schedule").insert(schedule).execute()

    # Assignments
    today = date.today()
    assignments = [
        {"user_id": uid, "class_id": cls_rows[0]["id"], "title": "Chapter 3 reading",
         "due_date": (today + timedelta(days=1)).isoformat(), "priority": "medium", "status": "todo"},
        {"user_id": uid, "class_id": cls_rows[1]["id"], "title": "Problem set 5",
         "due_date": (today + timedelta(days=4)).isoformat(), "priority": "high", "status": "in_progress"},
        {"user_id": uid, "class_id": cls_rows[2]["id"], "title": "Short story draft",
         "due_date": (today + timedelta(days=7)).isoformat(), "priority": "low", "status": "todo"},
    ]
    admin.table("assignments").insert(assignments).execute()

    # Notes
    admin.table("notes").insert([
        {"user_id": uid, "title": "Welcome to Mochi 🌸",
         "content": "# Hi!\n\nThis is your first note. Write in markdown — titles, lists, and links all work."},
    ]).execute()

    # Study sessions — a few days of history so charts have data.
    study = []
    for i, minutes in enumerate([45, 30, 0, 60, 25, 90, 15]):
        if minutes == 0:
            continue
        study.append({
            "user_id": uid,
            "class_id": cls_rows[i % len(cls_rows)]["id"],
            "duration": minutes,
            "date": (today - timedelta(days=6 - i)).isoformat(),
            "notes": "",
        })
    if study:
        admin.table("study_sessions").insert(study).execute()

    print(f"Seeded demo data for {email}.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python seed.py <email>")
        sys.exit(1)
    main(sys.argv[1])
