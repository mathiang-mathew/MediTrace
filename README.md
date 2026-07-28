# MediTrace
Python + SQLite CLI for patient records and HAI source-tracking

We built the shared database layer first. Created the SQLite schema (patients, care_details, infections, chw_visits) and the shared helper functions (get_connection, run_query, run_insert) that every other module would build against, then generated dummy sample data - [Mathiang]

Built each functional module in parallel, all working with the same shared schema and sample dataset (dummy data):
    Patient registration and care assignment - [Benigne]
    Infection and CHW visit logging (linked back to existing care details) - [Elnathan]
    Search and full patient history lookups - [Esther(lightstringset)]
    HAI pattern analysis (grouped counts by doctor, ward, equipment) - [Kabi]
    
    
Built the main menu and integration layer — the numbered CLI loop, global input validation, and the export function — wiring all the modules together into one program - [Esther].

For clarification purposes, MediTrace allows the same system permissions for its all authorized users because hospital computers are secured at the department level. Main users are nurses, doctors and other authorized/relevant hospital workers. Nurses (ward) specifically manage everyday patient’s registration, care assignments, and infection logging. Doctors and other relevant officers analyse HAI patterns, review patients’ records and export summary reports.

## How to Run

**Requirements:** Python 3 only — no external packages, everything uses the built-in `sqlite3` module.

1. Clone the repo and move into it:
```bash
   git clone https://github.com/mathiang-mathew/MediTrace.git
   cd MediTrace
```

2. Build the database (creates `meditrace.db` locally — it isn't tracked in git):
```bash
   python3 database.py
```

3. Generate the dummy dataset (safe to re-run any time for a clean reset):
```bash
   python3 seed_data.py
```

4. Run the program:
```bash
   python3 main.py
```

See `SCHEMA.md` for the database structure and design notes.
