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

Structure
---------
Two classes:

    HAIAnalyzer   one instance = the analysis of ONE factor (one column).
                  The column is validated once when the object is built and
                  then held on the object, so no method has to be given it
                  again and no method can be called with a column that was
                  never checked.

    AnalysisMenu  the sub-menu the user interacts with. It builds
                  HAIAnalyzer objects as needed and prints their tables.

Entry point for main.py:

    from analysis import AnalysisMenu
    result = AnalysisMenu().run()

Returns the string "HOME" if the user asked to go back to the main menu,
or None if they simply backed out. Either way main.py should re-display
the main menu; the distinction is there so navigation stays consistent
with the rest of the program.
"""

from collections import Counter

from database import run_query, split_list


class HAIAnalyzer:
    """The HAI analysis of one factor, e.g. ward, or equipment.

    Build one per column:

        analyzer = HAIAnalyzer("ward")
        analyzer.print_table()

    The column is checked in __init__ and stored as self.column. Every
    method reads it from there, so it is validated once instead of on
    every call, and an object that exists at all is an object whose
    column is safe to put in a query.
    """

    # ------------------------------------------------------------------
    # Class attributes: settings shared by every analyzer that is built.
    # These belong to the class rather than to any one object because
    # they do not change from one factor to the next.
    # ------------------------------------------------------------------

    # Columns stored as comma-separated text ("Ventilator 2, IV stand 5")
    # rather than one value per row. These cannot be counted with a plain
    # SQL GROUP BY; they have to be split first and counted in Python.
    LIST_COLUMNS = ("equipment", "medications", "procedures")

    # Columns this class is allowed to group by. Column names cannot be
    # passed to SQL as ? placeholders, so they are inserted into the query
    # text. This tuple is the safety check: nothing that isn't listed here
    # ever reaches a query, so no user input can be smuggled into SQL.
    ALLOWED_COLUMNS = ("ward", "doctor", "nurse") + LIST_COLUMNS

    # A group needs at least this many patients before its infection RATE
    # is treated as meaningful. Without it, a ward holding 2 patients where
    # both got infected shows a perfect 100% and beats every real ward on
    # the list. Two cases is not a pattern, it is a coincidence.
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

    # Names longer than this are cut short in the table so the columns
    # stay lined up.
    MAX_NAME_WIDTH = 31

    # ------------------------------------------------------------------
    # Building the object
    # ------------------------------------------------------------------

    def __init__(self, column):
        """Set up an analyzer for one column, refusing anything unapproved."""
        if column not in self.ALLOWED_COLUMNS:
            raise ValueError(
                f"'{column}' is not a column this class can group by."
            )
        self.column = column
        self.label = self.COLUMN_LABELS[column]
        self._results = None   # worked out on first use, then kept

    def __repr__(self):
        """What Python shows when the object is printed. Useful when testing."""
        return f"HAIAnalyzer({self.column!r})"

    @property
    def is_list_column(self):
        """True if this column holds several values in one cell."""
        return self.column in self.LIST_COLUMNS

    # ------------------------------------------------------------------
    # Counting
    # ------------------------------------------------------------------

    def _count_from(self, table):
        """Count rows in one table, grouped by this analyzer's column.

        Both counts work the same way and differ only in which table they
        read, so the logic lives here once and is called twice.
        """
        counts = Counter()

        if self.is_list_column:
            # One row can hold several items, so split and count each.
            for row in run_query(f"SELECT {self.column} FROM {table}"):
                items = split_list(row[self.column])
                if items:
                    counts.update(items)
                else:
                    counts[self.NOT_RECORDED] += 1
        else:
            rows = run_query(
                f"SELECT {self.column} AS value, COUNT(*) AS total "
                f"FROM {table} GROUP BY {self.column}"
            )
            for row in rows:
                value = row["value"] if row["value"] else self.NOT_RECORDED
                counts[value] += row["total"]

        return counts

    def count_cases(self):
        """Count logged HAI cases grouped by this factor.

        Returns a Counter mapping each value to the number of infection
        cases it appears in, e.g. Counter({'4b': 4, '3a': 2}).
        """
        return self._count_from("infections")

    def count_exposed(self):
        """Count how many patients were exposed to each value at all.

        This is the denominator for the rate. It comes from care_details --
        every patient with care assigned, infected or not -- so we can say
        "4 cases out of the 10 patients in that ward" instead of just "4".

        Counting rows here is safe because care_details holds exactly one
        row per patient: patient_id is UNIQUE and the row is UPDATEd in
        place as care changes rather than a new row being added (SCHEMA.md,
        "care_details"). So a row count is a patient count.

        If that ever changes and a patient can hold several care rows, this
        needs COUNT(DISTINCT patient_id) instead, and the list-column
        branch in _count_from needs the same treatment -- otherwise every
        denominator inflates and every rate reported here comes out too low.
        """

        return self._count_from("care_details")

    # ------------------------------------------------------------------
    # Ranking
    # ------------------------------------------------------------------

    def rank(self, refresh=False):
        """Build the full ranked result for this factor.

        Returns a list of dictionaries, sorted by number of cases (highest
        first), then alphabetically so the order never changes between runs:

            [{"name": "4b", "cases": 4, "patients": 10, "rate": 40.0,
              "rate_is_reliable": True, "rank": 1, "tied": False}, ...]

        Groups with zero cases are included, at the bottom.

        The result is kept on the object after the first call, so printing
        a table and then exporting it does not hit the database twice.
        Pass refresh=True to force it to be worked out again.
        """
        if self._results is not None and not refresh:
            return self._results

        case_counts = self.count_cases()
        patient_counts = self.count_exposed()

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
                # cases > patients means the infection record kept a snapshot
                # of care that no longer matches care_details. The percentage
                # comes out above 100, so it is not treated as reliable.
                "rate_is_reliable": (patients >= self.MIN_PATIENTS_FOR_RATE
                                     and cases <= patients),
            })

        results.sort(key=lambda item: (-item["cases"], item["name"]))
        self._add_ranks(results)

        self._results = results
        return results

    @staticmethod
    def _add_ranks(results):
        """Number the rows, sharing a rank where the case counts are equal.

        Ties give 1, 2, 2, 4 rather than 1, 2, 3, 4 -- two items in second
        place use up second and third, so the next one is fourth. This is
        the same convention used in sports standings.
        """
        previous_cases = None
        previous_rank = 0

        for position, item in enumerate(results, start=1):
            if position >= 2 and item["cases"] == previous_cases:
                item["rank"] = previous_rank
                item["tied"] = True
                results[position - 2]["tied"] = True
            else:
                item["rank"] = position
                item["tied"] = False
                previous_rank = position
                previous_cases = item["cases"]

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def _format_rate(self, item):
        """Turn the rate into something readable, with a warning marker."""
        if item["rate"] is None:
            return "-"
        if not item["rate_is_reliable"]:
            return f"{item['rate']}% *"
        return f"{item['rate']}%"

    def print_table(self):
        """Print the ranked table for this factor, plus a short reading of it."""
        results = self.rank()
        with_cases = [item for item in results if item["cases"] > 0]
        without_cases = [item for item in results if item["cases"] == 0]

        print()
        print(f"HAI cases by {self.label.lower()}")
        print("-" * 66)

        if not with_cases:
            print(f"  No infection cases have been logged against any "
                  f"{self.label.lower()} yet.")
            print("-" * 66)
            return

        print(f"  {'#':<4}{self.label:<32}{'Cases':>7}{'Patients':>10}{'Rate':>10}")
        for item in with_cases:
            marker = "=" if item["tied"] else " "
            print(f"  {str(item['rank']) + marker:<4}"
                  f"{item['name'][:self.MAX_NAME_WIDTH]:<32}"
                  f"{item['cases']:>7}"
                  f"{item['patients']:>10}"
                  f"{self._format_rate(item):>10}")

        print("-" * 66)
        self._print_reading(with_cases, without_cases)

    def _print_reading(self, with_cases, without_cases):
        """Say in one or two sentences what the table actually shows.

        This is the part that keeps the feature honest. The spec says
        MediTrace surfaces likely sources, it does not prove them -- so
        where the raw count and the rate disagree, both get reported
        instead of just the count, which is the number that looks
        convincing but can mislead.
        """
        total_cases = self.total_infection_records()
        top_by_cases = with_cases[0]

        reliable = [item for item in with_cases if item["rate_is_reliable"]]
        tied_at_top = [item for item in with_cases
                       if item["cases"] == top_by_cases["cases"]]

        # --- highest count -------------------------------------------------
        if len(tied_at_top) > 1:
            names = ", ".join(item["name"] for item in tied_at_top)
            print(f"  Highest count: a {len(tied_at_top)}-way tie at "
                  f"{top_by_cases['cases']} cases each, out of the "
                  f"{total_cases} cases logged hospital-wide ({names}).")
            
        else:
            print(f"  Highest count: {top_by_cases['name']} "
                  f"({top_by_cases['cases']} of the {total_cases} cases "
                  f"logged hospital-wide).")

        # --- highest rate --------------------------------------------------
        if reliable:
            best_rate = max(item["rate"] for item in reliable)
            leaders = [item for item in reliable if item["rate"] == best_rate]
            names_at_top = {item["name"] for item in tied_at_top}

            # Only worth saying if it points somewhere the count did not.
            if not all(item["name"] in names_at_top for item in leaders):
                if len(leaders) > 1:
                    names = ", ".join(item["name"] for item in leaders)
                    print(f"  Highest rate:  {len(leaders)}-way tie at "
                          f"{best_rate}% ({names}) -- investigate these "
                          f"alongside the count leader.")
                else:
                    leader = leaders[0]
                    print(f"  Highest rate:  {leader['name']} "
                          f"({leader['rate']}% of {leader['patients']} "
                          f"patients infected) -- investigate this alongside "
                          f"the count leader.")

        # --- groups with nothing logged against them ------------------------
        clean_names = [item["name"] for item in without_cases
                       if item["name"] != self.NOT_RECORDED]
        if clean_names:
            print(f"  No cases at all: {', '.join(clean_names)}")

        # --- footnotes, only when the marker they explain was printed -------
        if any(item["rate"] is not None and not item["rate_is_reliable"]
               for item in with_cases):
            print(f"  * percentage not reliable -- fewer than "
                  f"{self.MIN_PATIENTS_FOR_RATE} patients exposed, or more "
                  f"cases than current care records. Treat with caution.")

        if any(item["rate"] is None for item in with_cases):
            print("  - appears on an infection record but on no current care "
                  "record, so no rate can be worked out.")

    # ------------------------------------------------------------------
    # Facts about the data as a whole, not about one column
    # ------------------------------------------------------------------

    @staticmethod
    def total_infection_records():
        """How many infection cases have been logged, in total.

        Used as the denominator in the summary line. It cannot be worked
        out by adding up a ranked table: for equipment, medications and
        procedures one record contributes to several rows, so the column
        would sum to more than the number of records that exist.
        """
        return run_query("SELECT COUNT(*) AS total FROM infections")[0]["total"]

    @classmethod
    def has_any_infections(cls):
        """True if there is at least one infection case to analyse."""
        return cls.total_infection_records() > 0


class AnalysisMenu:
    """The 'Analyze HAI patterns' sub-menu.

    Holds the list of options and knows how to run the loop. It does not
    do any counting itself -- it builds HAIAnalyzer objects and asks them
    to print. Keeping the two apart means the analysis can be reused by
    the export feature without dragging the menu along with it.
    """

    # Each option maps to a title and the columns it prints.
    OPTIONS = {
        "1": ("Retrieve Procedures and Equipment with most HAI cases",
              ["procedures", "equipment"]),
        "2": ("Retrieve Wards with most HAI cases",
              ["ward"]),
        "3": ("Retrieve Hospital personnel associated with most HAI cases",
              ["doctor", "nurse"]),
        "4": ("Retrieve medication taken by most patients with HAI cases",
              ["medications"]),
    }

    def _print_options(self):
        print()
        print("===== Analyze HAI patterns =====")
        for key in sorted(self.OPTIONS):
            print(f"{key}. {self.OPTIONS[key][0]}")
        print()
        print("(Type Back to go one step Back)")
        print("(Type Home to go back to start)")

    def _show(self, choice):
        """Print every table belonging to one menu option."""
        title, columns = self.OPTIONS[choice]
        print()
        print(f"== {title} ==")
        for column in columns:
            HAIAnalyzer(column).print_table()

    def run(self):
        """Loop until the user chooses Back or Home.

        Returns "HOME" if they asked for the start of the program,
        otherwise None.
        """
        if not HAIAnalyzer.has_any_infections():
            print()
            print("No infection cases have been logged yet, so there is nothing")
            print("to analyse. Log a case first using option 3 on the main menu.")
            return None

        while True:
            self._print_options()
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

            if choice not in self.OPTIONS:
                print(f"'{choice}' is not one of the options. "
                      f"Enter a number from 1 to {len(self.OPTIONS)}, "
                      f"or Back / Home.")
                continue

            self._show(choice)


# Kept so main.py can carry on calling a plain function if that is how the
# rest of the program is wired. It just builds the menu object and runs it.
def analyze_hai_patterns():
    """Feature 8: the HAI pattern analysis sub-menu."""
    return AnalysisMenu().run()


if __name__ == "__main__":
    # Lets this module be run on its own for testing, without main.py.
    analyze_hai_patterns()