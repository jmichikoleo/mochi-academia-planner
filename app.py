"""Mochi Academia Planner — Flask backend.

Structure:
  - Auth routes (login/signup/logout)
  - Page routes (render templates, protected by @login_required)
  - API routes (/api/*) for async CRUD from the frontend

Auth model: after Supabase returns a session on login, we stash the access_token
and user_id in the Flask server-side session. Every protected route reconstructs
a per-user Supabase client using that token, so Postgres RLS enforces isolation.
"""
import os
from datetime import datetime, timedelta, date
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, jsonify, flash, send_from_directory,
)
from dotenv import load_dotenv

from supabase_client import get_anon_client, get_user_client

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-only-change-me")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
def login_required(view):
    """Redirect unauthenticated users to /login for HTML routes, 401 for /api."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "access_token" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"error": "unauthenticated"}), 401
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def sb():
    """Shortcut: user-scoped Supabase client for the current request."""
    return get_user_client(session["access_token"], session.get("refresh_token", ""))


def current_user_id():
    return session.get("user_id")


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        try:
            client = get_anon_client()
            res = client.auth.sign_in_with_password({"email": email, "password": password})
            session["access_token"] = res.session.access_token
            session["refresh_token"] = res.session.refresh_token
            session["user_id"] = res.user.id
            session["email"] = res.user.email
            return redirect(url_for("dashboard"))
        except Exception as e:
            flash(f"Login failed: {e}", "error")
            return render_template("login.html")
    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        try:
            client = get_anon_client()
            res = client.auth.sign_up({"email": email, "password": password})
            # Depending on Supabase settings, email confirmation may be required.
            if res.session:
                session["access_token"] = res.session.access_token
                session["refresh_token"] = res.session.refresh_token
                session["user_id"] = res.user.id
                session["email"] = res.user.email
                return redirect(url_for("dashboard"))
            flash("Account created — please check your email to confirm, then log in.", "info")
            return redirect(url_for("login"))
        except Exception as e:
            flash(f"Signup failed: {e}", "error")
            return render_template("signup.html")
    return render_template("signup.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Page routes — all require auth
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return redirect(url_for("dashboard") if "access_token" in session else url_for("login"))


# PWA: service worker must be served from the root so its scope covers the
# whole site. Browsers reject SW scripts served from /static/ trying to claim '/'.
@app.route("/sw.js")
def service_worker():
    return send_from_directory("static", "sw.js", mimetype="application/javascript")


@app.route("/manifest.webmanifest")
def manifest():
    return send_from_directory("static", "manifest.json", mimetype="application/manifest+json")


@app.route("/dashboard")
@login_required
def dashboard():
    today = date.today()
    weekday = today.weekday()  # Monday=0

    # Pull the data the dashboard needs in parallel-ish — Supabase-py is sync, so
    # just make the calls serially; they're small indexed queries.
    classes = sb().table("classes").select("*").eq("user_id", current_user_id()).execute().data or []

    today_schedule_rows = (
        sb().table("schedule").select("*, classes(name, color, professor, location)")
        .eq("day_of_week", weekday).execute().data or []
    )
    # Filter by class ownership (RLS + FK should guarantee this, but be defensive).
    class_ids = {c["id"] for c in classes}
    today_schedule = [s for s in today_schedule_rows if s.get("class_id") in class_ids]
    today_schedule.sort(key=lambda s: s["start_time"])

    week_end = today + timedelta(days=7)
    upcoming = (
        sb().table("assignments").select("*, classes(name, color)")
        .eq("user_id", current_user_id())
        .neq("status", "done")
        .lte("due_date", week_end.isoformat())
        .order("due_date", desc=False).limit(10).execute().data or []
    )

    # Study time today (sum durations in minutes).
    sessions_today = (
        sb().table("study_sessions").select("duration")
        .eq("user_id", current_user_id())
        .eq("date", today.isoformat()).execute().data or []
    )
    study_minutes_today = sum(s["duration"] for s in sessions_today)

    return render_template(
        "dashboard.html",
        classes=classes,
        today_schedule=today_schedule,
        upcoming=upcoming,
        study_minutes_today=study_minutes_today,
        deadline_count=len(upcoming),
    )


@app.route("/classes")
@login_required
def classes_page():
    rows = sb().table("classes").select("*").eq("user_id", current_user_id()).order("name").execute().data or []
    return render_template("classes.html", classes=rows)


@app.route("/classes/<class_id>")
@login_required
def class_detail(class_id):
    res = sb().table("classes").select("*").eq("id", class_id).single().execute()
    cls = res.data
    if not cls:
        flash("Class not found.", "error")
        return redirect(url_for("classes_page"))
    return render_template("class_detail.html", cls=cls)


@app.route("/schedule")
@login_required
def schedule_page():
    classes = sb().table("classes").select("*").eq("user_id", current_user_id()).execute().data or []
    # Only fetch schedule rows that belong to this user's classes.
    class_ids = [c["id"] for c in classes]
    entries = []
    if class_ids:
        entries = (
            sb().table("schedule").select("*, classes(name, color)")
            .in_("class_id", class_ids).execute().data or []
        )
    return render_template("schedule.html", classes=classes, entries=entries)


@app.route("/assignments")
@login_required
def assignments_page():
    classes = sb().table("classes").select("*").eq("user_id", current_user_id()).execute().data or []
    assignments = (
        sb().table("assignments").select("*, classes(name, color)")
        .eq("user_id", current_user_id())
        .order("due_date", desc=False).execute().data or []
    )
    return render_template("assignments.html", classes=classes, assignments=assignments)


@app.route("/gpa")
@login_required
def gpa_page():
    classes = sb().table("classes").select("*").eq("user_id", current_user_id()).execute().data or []
    records = (
        sb().table("gpa_records").select("*, classes(name)")
        .eq("user_id", current_user_id()).execute().data or []
    )
    return render_template("gpa.html", classes=classes, records=records)


@app.route("/lab")
@login_required
def lab_page():
    folders = sb().table("lab_folders").select("*").eq("user_id", current_user_id()).order("title").execute().data or []
    return render_template("lab.html", folders=folders)


@app.route("/lab/<folder_id>")
@login_required
def lab_folder_detail(folder_id):
    folder_res = sb().table("lab_folders").select("*").eq("id", folder_id).single().execute()
    folder = folder_res.data
    if not folder:
        flash("Folder not found.", "error")
        return redirect(url_for("lab_page"))
    entries = (
        sb().table("lab_entries").select("*").eq("folder_id", folder_id)
        .order("date", desc=True).execute().data or []
    )
    return render_template("lab_folder.html", folder=folder, entries=entries)


@app.route("/notes")
@login_required
def notes_page():
    notes = sb().table("notes").select("*").eq("user_id", current_user_id()).order("created_at", desc=True).execute().data or []
    return render_template("notes.html", notes=notes)


@app.route("/study")
@login_required
def study_page():
    classes = sb().table("classes").select("*").eq("user_id", current_user_id()).execute().data or []
    return render_template("study.html", classes=classes)


# ---------------------------------------------------------------------------
# API — Classes
# ---------------------------------------------------------------------------
@app.post("/api/classes")
@login_required
def api_create_class():
    data = request.get_json() or {}
    payload = {
        "user_id": current_user_id(),
        "name": data.get("name", "").strip(),
        "professor": data.get("professor", ""),
        "location": data.get("location", ""),
        "color": data.get("color", "#FADADD"),
    }
    if not payload["name"]:
        return jsonify({"error": "name is required"}), 400
    res = sb().table("classes").insert(payload).execute()
    return jsonify(res.data[0]), 201


@app.put("/api/classes/<class_id>")
@login_required
def api_update_class(class_id):
    data = request.get_json() or {}
    allowed = {k: data[k] for k in ("name", "professor", "location", "color") if k in data}
    res = sb().table("classes").update(allowed).eq("id", class_id).execute()
    return jsonify(res.data[0] if res.data else {}), 200


@app.delete("/api/classes/<class_id>")
@login_required
def api_delete_class(class_id):
    sb().table("classes").delete().eq("id", class_id).execute()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# API — Schedule
# ---------------------------------------------------------------------------
@app.post("/api/schedule")
@login_required
def api_create_schedule():
    data = request.get_json() or {}
    payload = {
        "class_id": data.get("class_id"),
        "day_of_week": int(data.get("day_of_week", 0)),
        "start_time": data.get("start_time"),
        "end_time": data.get("end_time"),
    }
    res = sb().table("schedule").insert(payload).execute()
    return jsonify(res.data[0]), 201


@app.delete("/api/schedule/<entry_id>")
@login_required
def api_delete_schedule(entry_id):
    sb().table("schedule").delete().eq("id", entry_id).execute()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# API — Assignments
# ---------------------------------------------------------------------------
@app.post("/api/assignments")
@login_required
def api_create_assignment():
    data = request.get_json() or {}
    payload = {
        "user_id": current_user_id(),
        "class_id": data.get("class_id") or None,
        "title": data.get("title", "").strip(),
        "due_date": data.get("due_date"),
        "priority": data.get("priority", "medium"),
        "status": data.get("status", "todo"),
    }
    if not payload["title"]:
        return jsonify({"error": "title is required"}), 400
    res = sb().table("assignments").insert(payload).execute()
    return jsonify(res.data[0]), 201


@app.put("/api/assignments/<aid>")
@login_required
def api_update_assignment(aid):
    data = request.get_json() or {}
    allowed = {k: data[k] for k in ("title", "class_id", "due_date", "priority", "status") if k in data}
    res = sb().table("assignments").update(allowed).eq("id", aid).execute()
    return jsonify(res.data[0] if res.data else {}), 200


@app.delete("/api/assignments/<aid>")
@login_required
def api_delete_assignment(aid):
    sb().table("assignments").delete().eq("id", aid).execute()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# API — GPA
# ---------------------------------------------------------------------------
@app.post("/api/gpa")
@login_required
def api_create_gpa():
    data = request.get_json() or {}
    payload = {
        "user_id": current_user_id(),
        "class_id": data.get("class_id") or None,
        "credits": float(data.get("credits", 0)),
        "grade": data.get("grade", ""),
    }
    res = sb().table("gpa_records").insert(payload).execute()
    return jsonify(res.data[0]), 201


@app.delete("/api/gpa/<gid>")
@login_required
def api_delete_gpa(gid):
    sb().table("gpa_records").delete().eq("id", gid).execute()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# API — Lab (folders, entries, files)
# ---------------------------------------------------------------------------
@app.post("/api/lab/folders")
@login_required
def api_create_folder():
    data = request.get_json() or {}
    payload = {
        "user_id": current_user_id(),
        "title": data.get("title", "").strip(),
        "description": data.get("description", ""),
    }
    if not payload["title"]:
        return jsonify({"error": "title is required"}), 400
    res = sb().table("lab_folders").insert(payload).execute()
    return jsonify(res.data[0]), 201


@app.delete("/api/lab/folders/<fid>")
@login_required
def api_delete_folder(fid):
    sb().table("lab_folders").delete().eq("id", fid).execute()
    return jsonify({"ok": True})


@app.post("/api/lab/entries")
@login_required
def api_create_entry():
    data = request.get_json() or {}
    payload = {
        "folder_id": data.get("folder_id"),
        "title": data.get("title", "").strip(),
        "date": data.get("date") or date.today().isoformat(),
        "summary": data.get("summary", ""),
        "notes": data.get("notes", ""),
    }
    if not payload["title"]:
        return jsonify({"error": "title is required"}), 400
    res = sb().table("lab_entries").insert(payload).execute()
    return jsonify(res.data[0]), 201


@app.put("/api/lab/entries/<eid>")
@login_required
def api_update_entry(eid):
    data = request.get_json() or {}
    allowed = {k: data[k] for k in ("title", "date", "summary", "notes") if k in data}
    res = sb().table("lab_entries").update(allowed).eq("id", eid).execute()
    return jsonify(res.data[0] if res.data else {}), 200


@app.delete("/api/lab/entries/<eid>")
@login_required
def api_delete_entry(eid):
    sb().table("lab_entries").delete().eq("id", eid).execute()
    return jsonify({"ok": True})


@app.post("/api/lab/files")
@login_required
def api_upload_file():
    """Uploads a file to Supabase Storage and records it in lab_files.

    Uses the service-role client for storage (bypasses storage RLS). The path
    includes the authenticated user_id, so server-side scoping is preserved.
    """
    from supabase_client import get_admin_client

    entry_id = request.form.get("entry_id")
    f = request.files.get("file")
    if not entry_id or not f:
        return jsonify({"error": "entry_id and file are required"}), 400

    try:
        safe_name = os.path.basename(f.filename).lstrip(".") or "upload"
        path = f"{current_user_id()}/{entry_id}/{safe_name}"
        content = f.read()
        content_type = f.mimetype or "application/octet-stream"

        admin = get_admin_client()
        admin.storage.from_("lab").upload(
            path=path,
            file=content,
            file_options={"content-type": content_type, "upsert": "true"},
        )
        public_url = admin.storage.from_("lab").get_public_url(path)

        row = sb().table("lab_files").insert({
            "entry_id": entry_id,
            "file_url": public_url,
            "file_type": content_type,
        }).execute()
        return jsonify(row.data[0]), 201
    except Exception as e:
        app.logger.exception("Upload failed")
        return jsonify({"error": str(e)}), 500

@app.get("/api/lab/entries/<eid>/files")
@login_required
def api_list_files(eid):
    res = sb().table("lab_files").select("*").eq("entry_id", eid).execute()
    return jsonify(res.data or [])


# ---------------------------------------------------------------------------
# API — Notes
# ---------------------------------------------------------------------------
@app.post("/api/notes")
@login_required
def api_create_note():
    data = request.get_json() or {}
    payload = {
        "user_id": current_user_id(),
        "title": data.get("title", "Untitled"),
        "content": data.get("content", ""),
    }
    res = sb().table("notes").insert(payload).execute()
    return jsonify(res.data[0]), 201


@app.put("/api/notes/<nid>")
@login_required
def api_update_note(nid):
    data = request.get_json() or {}
    allowed = {k: data[k] for k in ("title", "content") if k in data}
    res = sb().table("notes").update(allowed).eq("id", nid).execute()
    return jsonify(res.data[0] if res.data else {}), 200


@app.delete("/api/notes/<nid>")
@login_required
def api_delete_note(nid):
    sb().table("notes").delete().eq("id", nid).execute()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# API — Study sessions
# ---------------------------------------------------------------------------
@app.post("/api/study")
@login_required
def api_create_session():
    data = request.get_json() or {}
    payload = {
        "user_id": current_user_id(),
        "class_id": data.get("class_id") or None,
        "duration": int(data.get("duration", 0)),  # minutes
        "date": data.get("date") or date.today().isoformat(),
        "notes": data.get("notes", ""),
    }
    res = sb().table("study_sessions").insert(payload).execute()
    return jsonify(res.data[0]), 201


@app.get("/api/study/stats")
@login_required
def api_study_stats():
    """Returns daily totals for last 7 days + per-class totals for the same window."""
    today = date.today()
    start = today - timedelta(days=6)
    rows = (
        sb().table("study_sessions").select("*, classes(name, color)")
        .eq("user_id", current_user_id())
        .gte("date", start.isoformat()).execute().data or []
    )

    # Daily totals (always include all 7 days so the chart has consistent shape).
    daily = {(start + timedelta(days=i)).isoformat(): 0 for i in range(7)}
    per_class = {}
    for r in rows:
        daily[r["date"]] = daily.get(r["date"], 0) + r["duration"]
        cls = (r.get("classes") or {}).get("name") or "Uncategorized"
        per_class[cls] = per_class.get(cls, 0) + r["duration"]

    return jsonify({
        "daily": [{"date": d, "minutes": m} for d, m in daily.items()],
        "per_class": [{"name": k, "minutes": v} for k, v in per_class.items()],
    })


# ---------------------------------------------------------------------------
# Template context — make common helpers available in every template.
# ---------------------------------------------------------------------------
@app.context_processor
def inject_common():
    return {
        "current_email": session.get("email"),
        "today": date.today().isoformat(),
        "weekday_names": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    }


if __name__ == "__main__":
    app.run(debug=True, port=5050)
