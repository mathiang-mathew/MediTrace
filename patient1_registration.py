"""
patient_registration.py
-------------------------
Features 1-2 of MediTrace: patient registration and care assignment,
built as an object-oriented module.

Entry points for main.py (unchanged contract):
    from patient_registration import add_new_patient, assign_care_details
    result = add_new_patient()
    result = assign_care_details()

Features & Enhancements:
- StepRunner engine manages "Back" (previous prompt) and "Home" (main menu).
- Database-driven selection menus for Equipment, Medications, Procedures, 
  and Illness (fetches distinct values dynamically with an 'Other' fallback).
- Full OOP design without CSV/JSON dependencies (SQLite-native).
"""

import re
from database import run_query, run_insert

LIST_FIELD_HINT = " (comma-separated if entering custom text)"
NAV_HINT = " [Back/Home]: "

# Optional "+" and 1-3 digit country code, followed by exactly 10 digits.
CONTACT_PATTERN = re.compile(r"^(\+\d{1,3})?\d{10}$")

# Fallback pick-list if database care_details/infections tables are empty
DEFAULT_ILLNESS_OPTIONS = [
    "Malaria",
    "Typhoid",
    "Tuberculosis",
    "Pneumonia",
    "Hypertension",
    "Diabetes complications",
    "Postpartum care",
    "Road traffic accident injury",
    "Surgical site infection",
    "Catheter-associated UTI",
    "Ventilator-associated pneumonia",
    "Central line-associated infection",
    "Bloodstream infection",
]


class NavigationSignal(Exception):
    """Raised whenever the user types Back or Home at any prompt."""
    def __init__(self, destination):
        self.destination = destination  # "BACK" or "HOME"


def _check_nav(value):
    lowered = value.strip().lower()
    if lowered == "back":
        raise NavigationSignal("BACK")
    if lowered == "home":
        raise NavigationSignal("HOME")


# ------------------------------------------------------------- FieldReaders
class FieldReader:
    """Base class for every prompt in this module."""

    def __init__(self, prompt):
        self.prompt = prompt

    def read(self):
        while True:
            value = input(self.prompt).strip()
            _check_nav(value)
            if not value:
                print("This field cannot be empty. Please try again.")
                continue
            result = self.validate(value)
            if result is None:
                continue
            return result

    def validate(self, value):
        """Default: any non-blank value is accepted as-is."""
        return value


class LettersField(FieldReader):
    """For patient name, doctor, nurse -- letters and spaces only."""

    def validate(self, value):
        if not value.replace(" ", "").isalpha():
            print("This field must contain letters only (no numbers). Please try again.")
            return None
        return value


class StartsWithLetterField(FieldReader):
    """Ensures each item starts with an alphabetic character."""

    def __init__(self, prompt, is_list=False):
        super().__init__(prompt)
        self.is_list = is_list

    def validate(self, value):
        items = [item.strip() for item in value.split(",")] if self.is_list else [value]
        items = [item for item in items if item]
        if not items or any(not item[0].isalpha() for item in items):
            print("This field must start with a letter. Please try again.")
            return None
        return ", ".join(items) if self.is_list else value


class PositiveIntField(FieldReader):
    """For age -- must be a positive whole number."""

    def validate(self, value):
        if value.isdigit() and int(value) > 0:
            return int(value)
        print("Please enter a positive whole number.")
        return None


class NonNegativeIntField(FieldReader):
    """For number of visits -- 0 or more."""

    def validate(self, value):
        if value.isdigit():
            return int(value)
        print("Please enter a whole number (0 or more).")
        return None


class GenderField(FieldReader):
    def __init__(self, prompt="Enter gender (M for male & F for female)" + NAV_HINT):
        super().__init__(prompt)

    def validate(self, value):
        if value.upper() in ("M", "F"):
            return value.upper()
        print("Please enter M or F.")
        return None


class ContactField(FieldReader):
    """Exactly 10 digits with optional '+' country code."""

    def validate(self, value):
        if not CONTACT_PATTERN.match(value):
            print("Contact must be exactly 10 digits (a '+' and a 1-3 digit "
                  "country code may optionally come before them, e.g. "
                  "+250788123456). Please try again.")
            return None
        return value


class WardField(FieldReader):
    """Validates ward input against existing database records."""

    def __init__(self, prompt, db):
        super().__init__(prompt)
        self.db = db
        self.existing = db.get_existing_wards()
        if self.existing:
            print("Existing wards on file: " + ", ".join(self.existing))

    def validate(self, value):
        if not self.existing:
            return value
        match = next((w for w in self.existing if w.lower() == value.lower()), None)
        if match is None:
            print(f"'{value}' is not a ward on file. "
                  f"Please enter one of: {', '.join(self.existing)}.")
            return None
        return match


class MultiSelectDBField:
    """
    Displays DB options for Equipment, Medications, Procedures, or Illness.
    Allows toggling options or picking 'Other' for custom entry, returning comma-separated strings.
    """

    def __init__(self, category_name, db_items, prompt_hint=NAV_HINT):
        self.category_name = category_name
        self.options = db_items
        self.prompt_hint = prompt_hint

    def read(self):
        selected_items = []
        other_num = len(self.options) + 1

        while True:
            print(f"\n--- Select {self.category_name} ---")
            if self.options:
                for idx, item in enumerate(self.options, start=1):
                    status = "[X]" if item in selected_items else "[ ]"
                    print(f"  {idx}. {status} {item}")
                print(f"  {other_num}. Other (specify custom value)")
            else:
                print("  (No existing records found in database)")
                print(f"  1. Other (specify custom value)")
                other_num = 1

            print("  0. Done selecting")

            raw_input = input(f"Choose option (0-{other_num})" + self.prompt_hint).strip()
            _check_nav(raw_input)

            if raw_input == "0":
                if not selected_items:
                    print(f"Please select at least one {self.category_name.lower()} or enter 'Other'.")
                    continue
                return ", ".join(selected_items)

            if not raw_input.isdigit():
                print(f"Please enter a valid choice between 0 and {other_num}.")
                continue

            choice = int(raw_input)

            if choice == other_num:
                custom_prompt = f"Enter custom {self.category_name.lower()}" + self.prompt_hint
                custom_val = StartsWithLetterField(custom_prompt, is_list=True).read()
                custom_items = [i.strip() for i in custom_val.split(",") if i.strip()]
                for item in custom_items:
                    if item not in selected_items:
                        selected_items.append(item)
                        print(f" -> Added: {item}")
            elif 1 <= choice <= len(self.options):
                chosen_item = self.options[choice - 1]
                if chosen_item in selected_items:
                    selected_items.remove(chosen_item)
                    print(f" -> Removed: {chosen_item}")
                else:
                    selected_items.append(chosen_item)
                    print(f" -> Added: {chosen_item}")
            else:
                print(f"Invalid option. Enter a number between 0 and {other_num}.")


class IllnessField:
    """Presents existing illnesses or defaults, plus an 'Other' option."""

    def __init__(self, db):
        self.db = db
        db_illnesses = self.db.get_existing_illnesses()
        # Merge DB results with default common illnesses
        combined = list(dict.fromkeys(db_illnesses + DEFAULT_ILLNESS_OPTIONS))
        self.options = combined

    def read(self):
        other_num = len(self.options) + 1
        while True:
            print("\nSelect the patient's illness/diagnosis:")
            for i, name in enumerate(self.options, start=1):
                print(f"  {i}. {name}")
            print(f"  {other_num}. Other (specify custom illness)")

            raw_choice = FieldReader(f"Enter a number 1-{other_num}" + NAV_HINT).read()

            if not raw_choice.isdigit():
                print(f"Please enter a number between 1 and {other_num}.")
                continue

            choice_num = int(raw_choice)
            if 1 <= choice_num <= len(self.options):
                return self.options[choice_num - 1]
            if choice_num == other_num:
                return StartsWithLetterField("Enter the custom illness name" + NAV_HINT).read()
            print(f"Please enter a number between 1 and {other_num}.")


# ---------------------------------------------------------- Step / StepRunner
class Step:
    """Represents a single prompt in a multi-step sequence."""

    def __init__(self, key, make_reader, post_check=None):
        self.key = key
        self.make_reader = make_reader
        self.post_check = post_check


class StepRunner:
    """Executes a list of Steps with Step-by-Step Back and Home navigation."""

    def __init__(self, steps):
        self.steps = steps

    def run(self):
        answers = {}
        index = 0
        while index < len(self.steps):
            step = self.steps[index]
            reader = step.make_reader(answers)
            try:
                value = reader.read()
            except NavigationSignal as nav:
                if nav.destination == "HOME":
                    return "HOME"
                if index == 0:
                    return None
                index -= 1
                continue

            if step.post_check:
                ok, message = step.post_check(value, answers)
                if not ok:
                    if message:
                        print(message)
                    continue

            answers[step.key] = value
            index += 1
        return answers


# --------------------------------------------------------------- Database Layer
class MediTraceDatabase:
    """Encapsulates all direct SQL operations."""

    def patient_name_exists(self, name):
        rows = run_query("SELECT patient_id FROM patients WHERE LOWER(name) = LOWER(?)", (name,))
        return len(rows) > 0

    def get_patient_by_id(self, patient_id):
        rows = run_query("SELECT * FROM patients WHERE patient_id = ?", (patient_id,))
        return rows[0] if rows else None

    def get_care_details(self, patient_id):
        rows = run_query("SELECT * FROM care_details WHERE patient_id = ?", (patient_id,))
        return rows[0] if rows else None

    def get_existing_wards(self):
        rows_care = run_query("SELECT DISTINCT ward FROM care_details WHERE ward IS NOT NULL AND TRIM(ward) != ''")
        rows_inf = run_query("SELECT DISTINCT ward FROM infections WHERE ward IS NOT NULL AND TRIM(ward) != ''")
        wards = {row["ward"] for row in rows_care} | {row["ward"] for row in rows_inf}
        return sorted(list(wards))

    def _get_distinct_list(self, column, tables=("care_details", "infections")):
        vals = set()
        for table in tables:
            try:
                rows = run_query(f"SELECT DISTINCT {column} FROM {table} WHERE {column} IS NOT NULL AND TRIM({column}) != ''")
                for r in rows:
                    raw_val = r[column] if isinstance(r, dict) else r[0]
                    for item in raw_val.split(","):
                        cleaned = item.strip()
                        if cleaned:
                            vals.add(cleaned)
            except Exception:
                continue
        return sorted(list(vals))

    def get_existing_illnesses(self):
        return self._get_distinct_list("illness", tables=("patients", "infections"))

    def get_existing_equipment(self):
        return self._get_distinct_list("equipment")

    def get_existing_medications(self):
        return self._get_distinct_list("medications")

    def get_existing_procedures(self):
        return self._get_distinct_list("procedures")

    def insert_patient(self, name, age, gender, illness, contact, num_visits):
        return run_insert(
            "INSERT INTO patients (name, age, gender, illness, contact, num_visits) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (name, age, gender, illness, contact, num_visits),
        )

    def upsert_care_details(self, patient_id, ward, doctor, nurse, equipment, medications, procedures):
        if self.get_care_details(patient_id):
            run_insert(
                "UPDATE care_details SET ward=?, doctor=?, nurse=?, equipment=?, "
                "medications=?, procedures=?, last_updated=datetime('now') WHERE patient_id=?",
                (ward, doctor, nurse, equipment, medications, procedures, patient_id),
            )
            return "updated"
        run_insert(
            "INSERT INTO care_details (patient_id, ward, doctor, nurse, equipment, medications, procedures) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (patient_id, ward, doctor, nurse, equipment, medications, procedures),
        )
        return "inserted"


# ---------------------------------------------------------------- Service Layer
class PatientRegistrationService:
    """Service object housing Feature 1 and Feature 2."""

    def __init__(self, db=None):
        self.db = db or MediTraceDatabase()

    def add_new_patient(self):
        print("\n== Add New Patient ==")
        print("(Type Back to go one step Back)")
        print("(Type Home to go back to the main menu)")

        def name_duplicate_check(value, answers):
            if self.db.patient_name_exists(value):
                return False, (
                    f"A patient named '{value}' already exists. "
                    f"Use Search / filter to find their ID instead, or enter a different name."
                )
            return True, None

        steps = [
            Step("name", lambda a: LettersField("Enter patient name" + NAV_HINT), post_check=name_duplicate_check),
            Step("illness", lambda a: IllnessField(self.db)),
            Step("age", lambda a: PositiveIntField("Enter age" + NAV_HINT)),
            Step("gender", lambda a: GenderField()),
            Step("contact", lambda a: ContactField("Enter contact (10 digits, e.g. 0788123456)" + NAV_HINT)),
            Step("num_visits", lambda a: NonNegativeIntField("Enter number of visits so far (0 if first)" + NAV_HINT)),
        ]

        result = StepRunner(steps).run()

        if result == "HOME":
            return "HOME"
        if result is None:
            print("Cancelled. Returning to the main menu...")
            return None

        new_id = self.db.insert_patient(
            result["name"], result["age"], result["gender"],
            result["illness"], result["contact"], result["num_visits"],
        )
        print(f"\nNew Patient info saved successfully! Assigned Patient ID: {new_id}.")
        print("Returning to the main menu...")
        return None

    def assign_care_details(self):
        print("\n== Assign Care Details ==")
        print("(Type Back to go one step Back)")
        print("(Type Home to go back to the main menu)")

        def patient_id_check(value, answers):
            if not value.isdigit():
                return False, "Patient ID must be a number. Please try again."
            patient = self.db.get_patient_by_id(int(value))
            if not patient:
                return False, f"No patient found with ID {value}. Please try again."
            
            p_name = patient['name'] if isinstance(patient, dict) else patient[1]
            p_id = patient['patient_id'] if isinstance(patient, dict) else patient[0]
            answers["patient"] = patient
            print(f"\nAssigning care details for: {p_name} (ID: {p_id})")
            return True, None

        steps = [
            Step("patient_id", lambda a: FieldReader("Enter patient ID" + NAV_HINT), post_check=patient_id_check),
            Step("ward", lambda a: WardField("Enter ward" + NAV_HINT, self.db)),
            Step("doctor", lambda a: LettersField("Enter doctor's name" + NAV_HINT)),
            Step("nurse", lambda a: LettersField("Enter nurse's name" + NAV_HINT)),
            Step("equipment", lambda a: MultiSelectDBField("Equipment", self.db.get_existing_equipment())),
            Step("medications", lambda a: MultiSelectDBField("Medications", self.db.get_existing_medications())),
            Step("procedures", lambda a: MultiSelectDBField("Procedures", self.db.get_existing_procedures())),
        ]

        result = StepRunner(steps).run()

        if result == "HOME":
            return "HOME"
        if result is None:
            print("Cancelled. Returning to the main menu...")
            return None

        patient = result["patient"]
        p_id = patient['patient_id'] if isinstance(patient, dict) else patient[0]

        outcome = self.db.upsert_care_details(
            p_id, result["ward"], result["doctor"], result["nurse"],
            result["equipment"], result["medications"], result["procedures"],
        )
        if outcome == "updated":
            print("\nCare details updated successfully! Returning to the main menu...")
        else:
            print("\nCare details saved successfully! Returning to the main menu...")
        return None


# ------------------------------------------------- Main Entry Points
_service = PatientRegistrationService()


def add_new_patient():
    return _service.add_new_patient()


def assign_care_details():
    return _service.assign_care_details()


if __name__ == "__main__":
    add_new_patient()
    assign_care_details()