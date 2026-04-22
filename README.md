# Mochi Academia Planner 🌸

A clean, pink-pastel university planner built with Flask + Supabase. Classes,
schedule, assignments, GPA, lab/research folders with file uploads, markdown
notes, and a YPT-style study timer with charts.

## Stack

- **Backend:** Flask
- **Database / Auth / Storage:** Supabase (Postgres + RLS, GoTrue, Object Storage)
- **Frontend:** Jinja templates, Tailwind (CDN), vanilla JS, Chart.js

## Getting started

### 1. Install dependencies

```bash
cd mochi-academia-planner
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Fill in SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY, FLASK_SECRET_KEY
```

### 3. Create the schema in Supabase

In the Supabase SQL editor, run `supabase/schema.sql` once. This creates all
tables and enables row-level security so each user only sees their own data.

Then in **Storage**, create a bucket named `lab` (public read) and add the
policies at the bottom of `schema.sql`.

### 4. Run

```bash
python app.py
# -> http://127.0.0.1:5050
```

### 5. (Optional) seed demo data

```bash
# After signing up in the UI:
python seed.py your@email.com
```

## Structure

```
mochi-academia-planner/
├── app.py                  # Flask routes + API
├── supabase_client.py      # Supabase client factories (admin / anon / per-user)
├── seed.py                 # Demo data generator
├── supabase/
│   └── schema.sql          # Tables + RLS policies
├── templates/
│   ├── base.html           # Sidebar layout, theme, flash messages
│   ├── login.html / signup.html
│   ├── dashboard.html
│   ├── classes.html / class_detail.html
│   ├── schedule.html       # Weekly grid, current-class highlight
│   ├── assignments.html    # CRUD + filters + overdue highlight
│   ├── gpa.html            # Cumulative GPA calculator
│   ├── lab.html / lab_folder.html  # Research folders + entries + uploads
│   ├── notes.html          # Markdown editor with autosave
│   └── study.html          # Timer + daily/per-class charts
└── static/
    ├── css/app.css
    └── js/
        ├── app.js          # Sidebar + modal helpers
        ├── timer.js        # Study session timer (localStorage-backed)
        └── charts.js       # Chart.js setup
```

## How auth works

- Supabase GoTrue handles email/password signup + login.
- On login, the access token and user id are stored in the Flask session.
- Every protected route builds a per-request Supabase client that passes the
  user's JWT to PostgREST, so RLS policies (`user_id = auth.uid()`) enforce
  isolation automatically.
- There is a service-role client too — used only by `seed.py`.

## Extending

- **Per-class file uploads:** mirror the lab `upload` handler, keyed on class_id.
- **Rich-text notes:** drop in a library like EasyMDE and point it at `#note-content`.
- **Push notifications:** replace the in-UI deadline banner with a scheduled
  email via a Supabase Edge Function.
