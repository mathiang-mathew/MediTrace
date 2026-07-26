# MediTrace — Database Schema & Setup

This is the foundation the rest of the team builds their features on. Read
this before writing your module so everyone's queries agree on column names.

## Files

| File | What it does |
|---|---|
| `database.py` | Creates the SQLite database + tables, and holds the three helper functions everyone imports |
| `seed_data.py` | Fills the database with ~28 realistic dummy patients (no real patient data anywhere) |
| `meditrace.db` | The actual database file — already created and seeded, ready to use |

## Getting started

You don't need to run anything to get going — `meditrace.db` is already
built and seeded. Just import from `database.py` in your own file:

```python
from database import get_connection, run_query, run_insert, split_list
```

If you ever want a fresh copy of the dummy data (e.g. after testing some
inserts of your own), just re-run:

```bash
python3 seed_data.py
```

It wipes and rebuilds all four tables from scratch. The random seed is
fixed, so everyone gets the *same* dummy data — if your analysis shows
"Ward 4b has the most HAI cases," mine will show the same thing.

## The three functions you'll use everywhere

- **`run_query(query, params)`** — for SELECT statements. Returns a list of
  rows you can treat like dicts: `row["name"]`, `row["ward"]`, etc.
- **`run_insert(query, params)`** — for INSERT / UPDATE / DELETE. Commits
  automatically, returns the new row's id (INSERT) or rows affected
  (UPDATE/DELETE).
- **`split_list(field_value)`** — turns a comma-separated field like
  `"Ventilator 2, IV stand 5"` into `["Ventilator 2", "IV stand 5"]`. You'll
  need this for equipment/medications/procedures — see below.

Always use `?` placeholders, never f-strings, when passing values into a
query — it avoids SQL injection and handles quoting for you:

```python
rows = run_query("SELECT * FROM patients WHERE ward = ?", ("4b",))
new_id = run_insert("INSERT INTO patients (name, age, gender) VALUES (?, ?, ?)",
                     ("David Boyo", 34, "M"))
```

## The four tables

### `patients`
| Column | Type | Notes |
|---|---|---|
| patient_id | INTEGER PK | auto-increments |
| name | TEXT | required |
| age | INTEGER | required, must be > 0 |
| gender | TEXT | 'M' or 'F' |
| illness | TEXT | |
| contact | TEXT | |
| num_visits | INTEGER | defaults to 0 |
| created_at | TEXT | auto-filled timestamp |

### `care_details`
One row per patient — **this row gets UPDATEd in place** as care changes,
it isn't a new row each time (`patient_id` is UNIQUE). This matches the
spec's "these can be updated as care changes."

| Column | Type | Notes |
|---|---|---|
| care_id | INTEGER PK | |
| patient_id | INTEGER | UNIQUE, FK -> patients |
| ward | TEXT | required |
| doctor | TEXT | required |
| nurse | TEXT | |
| equipment | TEXT | comma-separated, e.g. `"Ventilator 2, IV stand 5"` |
| medications | TEXT | comma-separated |
| procedures | TEXT | comma-separated |
| last_updated | TEXT | auto-filled timestamp |

### `infections`
One row per logged HAI case. **This is a snapshot**, not a link — when
Elnathan's `log_infection_case()` runs, it copies the patient's *current*
ward/doctor/nurse/equipment/medications/procedures from `care_details` into
this row at that moment. That's what the spec means by "automatically
linked from their existing record." We snapshot instead of joining live so
that if a patient's ward changes six months later, old infection records
still correctly reflect what was true when the infection happened.

| Column | Type | Notes |
|---|---|---|
| infection_id | INTEGER PK | |
| patient_id | INTEGER | FK -> patients |
| infection_type | TEXT | required |
| date_of_onset | TEXT | required, `YYYY-MM-DD` |
| ward, doctor, nurse, equipment, medications, procedures | TEXT | copied from care_details at logging time |
| logged_at | TEXT | auto-filled timestamp |

### `chw_visits`
| Column | Type | Notes |
|---|---|---|
| visit_id | INTEGER PK | |
| patient_id | INTEGER | FK -> patients |
| visit_date | TEXT | required |
| reason | TEXT | required |
| notes | TEXT | |
| next_followup_date | TEXT | compare against today's date for Feature 6 |

## One design decision worth knowing (for Kabi's analysis module especially)

`equipment`, `medications`, and `procedures` are stored as comma-separated
text rather than separate tables, since a patient can have more than one of
each and full junction tables would be overkill for this project's scope.

That means grouping by ward or doctor is a plain SQL `GROUP BY` on
`infections`, but grouping by equipment or procedure needs `split_list()`
first, then counting in Python — SQL can't split a comma-separated column
on its own. Example for the "Retrieve Procedures and Equipment with most
HAI cases" analysis option:

```python
from collections import Counter
from database import run_query, split_list

rows = run_query("SELECT equipment FROM infections")
counts = Counter()
for row in rows:
    counts.update(split_list(row["equipment"]))

for equipment, n in counts.most_common():
    print(equipment, n)
```

## Sanity-checked

The seeded database has been verified: 28 patients, 28 care_details rows,
11 infection cases, 46 CHW visits, zero orphaned foreign keys, and the
"Ventilator 2" and "Ward 4b" bias mentioned above shows up in the data —
useful for demoing that the analysis feature actually surfaces something
meaningful.
