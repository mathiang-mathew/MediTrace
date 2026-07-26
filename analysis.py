"""
analysis.py
-----------
Feature 8 of MediTrace: HAI pattern analysis.

Owner: Kabi Jean Paul

This module answers one question: when patients acquire healthcare-associated
infections, what do those cases have in common? It groups every logged
infection case by ward, doctor, nurse, equipment, medication or procedure,
counts them, and prints a ranked table so the facility can see where to
investigate first.

Two things it deliberately does beyond a plain count:

1. It shows a RATE, not just a raw count. A big ward will top a raw-count
   ranking simply for holding more patients. Ward 4b having the most cases
   means little if 4b also holds a third of the hospital. So every table
   shows cases, the number of patients exposed to that factor, and the
   percentage. See MIN_PATIENTS_FOR_RATE below.

2. It reports groups with ZERO cases too. A ward with no infections at all
   is useful information -- it may be doing something the others aren't.

Entry point for main.py:

    from analysis import analyze_hai_patterns
    result = analyze_hai_patterns()

Returns the string "HOME" if the user asked to go back to the main menu,
or None if they simply backed out. Either way main.py should re-display
the main menu; the distinction is there so navigation stays consistent
with the rest of the program.
"""

from collections import Counter

from database import run_query, split_list


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

# Columns stored as comma-separated text ("Ventilator 2, IV stand 5") rather
# than one value per row. These cannot be counted with a plain SQL GROUP BY;
# they have to be split first and counted in Python. See SCHEMA.md.
LIST_COLUMNS = ("equipment", "medications", "procedures")

# Columns this module is allowed to group by. Column names cannot be passed
# to SQL as ? placeholders, so they are inserted into the query text. This
# tuple is the safety check: nothing that isn't listed here ever reaches a
# query, so no user input can be smuggled into SQL.
ALLOWED_COLUMNS = ("ward", "doctor", "nurse") + LIST_COLUMNS

# A group needs at least this many patients before its infection RATE is
# treated as meaningful. Without it, a ward holding 2 patients where both
# got infected shows a perfect 100% and beats every real ward on the list.
# Two cases is not a pattern, it is a coincidence.
MIN_PATIENTS_FOR_RATE = 5

# Shown in place of a missing value (nurse is optional in the schema).
NOT_RECORDED = "(not recorded)"

# Human-readable headings for each column.
COLUMN_LABELS = {
    "ward": "Ward",
    "doctor": "Doctor",
    "nurse": "Nurse",
    "equipment": "Equipment",
    "medications": "Medication",
    "procedures": "Procedure",
}


# --------------------------------------------------------------------------
# Counting
# --------------------------------------------------------------------------

def _check_column(column):
    """Stop any column name that isn't on the approved list."""
    if column not in ALLOWED_COLUMNS:
        raise ValueError(f"'{column}' is not a column this module can group by.")


def count_infection_cases(column):
    """Count logged HAI cases grouped by one factor.

    Returns a Counter mapping each value to the number of infection cases
    it appears in, e.g. Counter({'4b': 4, '3a': 2}).
    """
    _check_column(column)
    counts = Counter()

    if column in LIST_COLUMNS:
        # One infection row can hold several items, so split and count each.
        for row in run_query(f"SELECT {column} FROM infections"):
            items = split_list(row[column])
            if items:
                counts.update(items)
            else:
                counts[NOT_RECORDED] += 1
    else:
        rows = run_query(
            f"SELECT {column} AS value, COUNT(*) AS total "
            f"FROM infections GROUP BY {column}"
        )
        for row in rows:
            value = row["value"] if row["value"] else NOT_RECORDED
            counts[value] += row["total"]

    return counts


def count_exposed_patients(column):
    """Count how many patients were exposed to each factor at all.

    This is the denominator for the rate. It comes from care_details --
    every patient with care assigned, infected or not -- so we can say
    "4 cases out of the 10 patients in that ward" instead of just "4".
    """
    _check_column(column)
    counts = Counter()

    if column in LIST_COLUMNS:
        for row in run_query(f"SELECT {column} FROM care_details"):
            items = split_list(row[column])
            if items:
                counts.update(items)
            else:
                counts[NOT_RECORDED] += 1
    else:
        rows = run_query(
            f"SELECT {column} AS value, COUNT(*) AS total "
            f"FROM care_details GROUP BY {column}"
        )
        for row in rows:
            value = row["value"] if row["value"] else NOT_RECORDED
            counts[value] += row["total"]

    return counts


def rank_by(column):
    """Build the full ranked result for one factor.

    Returns a list of dictionaries, sorted by number of cases (highest
    first), then alphabetically so the order never changes between runs:

        [{"name": "4b", "cases": 4, "patients": 10, "rate": 40.0,
          "rate_is_reliable": True, "rank": 1}, ...]

    Groups with zero cases are included, at the bottom. main.py and the
    export feature can both use this without touching the printing code.
    """
    _check_column(column)

    case_counts = count_infection_cases(column)
    patient_counts = count_exposed_patients(column)

    # Every value that appears in either table gets a row.
    all_values = set(case_counts) | set(patient_counts)

    results = []
    for value in all_values:
        cases = case_counts.get(value, 0)
        patients = patient_counts.get(value, 0)

        if patients > 0:
            rate = round(cases / patients * 100, 1)
        else:
            # Appears on an infection record but not on any current care
            # record -- possible because infections store a snapshot.
            rate = None

        results.append({
            "name": value,
            "cases": cases,
            "patients": patients,
            "rate": rate,
            "rate_is_reliable": patients >= MIN_PATIENTS_FOR_RATE,
        })

    results.sort(key=lambda item: (-item["cases"], item["name"]))

    # Shared rank numbers for ties: 1, 2, 2, 4 rather than 1, 2, 3, 4.
    previous_cases = None
    previous_rank = 0
    for position, item in enumerate(results, start=1):
        if item["cases"] == previous_cases:
            item["rank"] = previous_rank
            item["tied"] = True
            results[position - 2]["tied"] = True
        else:
            item["rank"] = position
            item["tied"] = False
            previous_rank = position
            previous_cases = item["cases"]

    return results


# --------------------------------------------------------------------------
# Display
# --------------------------------------------------------------------------

def _format_rate(item):
    """Turn the rate into something readable, with a warning marker."""
    if item["rate"] is None:
        return "-"
    if not item["rate_is_reliable"]:
        return f"{item['rate']}% *"
    return f"{item['rate']}%"


def print_ranked_table(column, results=None):
    """Print one ranked table for a factor, plus a short reading of it."""
    _check_column(column)
    if results is None:
        results = rank_by(column)

    label = COLUMN_LABELS[column]
    with_cases = [item for item in results if item["cases"] > 0]
    without_cases = [item for item in results if item["cases"] == 0]

    print()
    print(f"HAI cases by {label.lower()}")
    print("-" * 66)

    if not with_cases:
        print(f"  No infection cases have been logged against any {label.lower()} yet.")
        print("-" * 66)
        return

    print(f"  {'#':<4}{label:<32}{'Cases':>7}{'Patients':>10}{'Rate':>10}")
    for item in with_cases:
        marker = "=" if item["tied"] else " "
        print(f"  {str(item['rank']) + marker:<4}"
              f"{item['name'][:31]:<32}"
              f"{item['cases']:>7}"
              f"{item['patients']:>10}"
              f"{_format_rate(item):>10}")

    print("-" * 66)
    _print_reading(label, with_cases, without_cases)


def _print_reading(label, with_cases, without_cases):
    """Say in one or two sentences what the table actually shows.

    This is the part that keeps the feature honest. The spec says MediTrace
    surfaces likely sources, it does not prove them -- so where the raw
    count and the rate disagree, both get reported instead of just the
    count, which is the number that looks convincing but can mislead.
    """
    total_cases = sum(item["cases"] for item in with_cases)
    top_by_cases = with_cases[0]

    reliable = [item for item in with_cases if item["rate_is_reliable"]]
    top_by_rate = max(reliable, key=lambda item: item["rate"]) if reliable else None

    tied_at_top = [item for item in with_cases if item["cases"] == top_by_cases["cases"]]

    if len(tied_at_top) > 1:
        names = ", ".join(item["name"] for item in tied_at_top)
        print(f"  Highest count: a {len(tied_at_top)}-way tie at "
              f"{top_by_cases['cases']} cases ({names}).")
    else:
        print(f"  Highest count: {top_by_cases['name']} "
              f"({top_by_cases['cases']} of {total_cases} logged cases).")

    if top_by_rate and top_by_rate["name"] != top_by_cases["name"]:
        print(f"  Highest rate:  {top_by_rate['name']} "
              f"({top_by_rate['rate']}% of its {top_by_rate['patients']} patients "
              f"infected) -- investigate this alongside the count leader.")

    if without_cases:
        clean = ", ".join(item["name"] for item in without_cases)
        print(f"  No cases at all: {clean}")

    if any(not item["rate_is_reliable"] for item in with_cases):
        print(f"  * fewer than {MIN_PATIENTS_FOR_RATE} patients exposed -- "
              f"percentage not reliable, treat with caution.")


def has_any_infections():
    """True if there is at least one infection case to analyse."""
    return run_query("SELECT COUNT(*) AS total FROM infections")[0]["total"] > 0


# --------------------------------------------------------------------------
# Menu
# --------------------------------------------------------------------------

# Each option prints one or two tables.
ANALYSIS_OPTIONS = {
    "1": ("Retrieve Procedures and Equipment with most HAI cases",
          ["procedures", "equipment"]),
    "2": ("Retrieve Wards with most HAI cases",
          ["ward"]),
    "3": ("Retrieve Hospital personnel associated with most HAI cases",
          ["doctor", "nurse"]),
    "4": ("Retrieve medication taken by most patients with HAI cases",
          ["medications"]),
}


def _print_menu():
    print()
    print("===== Analyze HAI patterns =====")
    for key in sorted(ANALYSIS_OPTIONS):
        print(f"{key}. {ANALYSIS_OPTIONS[key][0]}")
    print()
    print("(Type Back to go one step Back)")
    print("(Type Home to go back to start)")


def analyze_hai_patterns():
    """Feature 8: the HAI pattern analysis sub-menu.

    Loops until the user chooses Back or Home. Returns "HOME" if they
    asked for the start of the program, otherwise None.
    """
    if not has_any_infections():
        print()
        print("No infection cases have been logged yet, so there is nothing")
        print("to analyse. Log a case first using option 3 on the main menu.")
        return None

    while True:
        _print_menu()
        try:
            choice = input("Enter your choice: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            # Ctrl+C or Ctrl+D should return to the menu quietly rather
            # than dumping a Python traceback in front of a health worker.
            print()
            return None

        if choice == "home":
            return "HOME"
        if choice in ("back", "0", ""):
            return None

        if choice not in ANALYSIS_OPTIONS:
            print(f"'{choice}' is not one of the options. "
                  f"Enter a number from 1 to {len(ANALYSIS_OPTIONS)}, "
                  f"or Back / Home.")
            continue

        title, columns = ANALYSIS_OPTIONS[choice]
        print()
        print(f"== {title} ==")
        for column in columns:
            print_ranked_table(column)


if __name__ == "__main__":
    # Lets this module be run on its own for testing, without main.py.
    analyze_hai_patterns()
