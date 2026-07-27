"""
patient_registration.py
-------------------------

Entry points for main.py:
    from patient_registration import add_new_patient, assign_care_details
    result = add_new_patient()
    result = assign_care_details()

Both return "HOME" if the user typed Home to jump back to the start of
the program, or None otherwise -- the same convention analysis.py uses
for analyze_hai_patterns(), so main.py can handle both the same way.

Validation rules, field by field:
    - patient name, doctor, nurse    -> letters only (no digits at all)
    - illness, equipment, medications,
      procedures                     -> must START with a letter
      (each comma-separated item checked individually for the
      list fields: equipment, medications, procedures)
    - age                            -> positive whole number
    - contact                       -> digits only
    - ward number                   -> digits only
    - gender                        -> M or F only
An existing patient cannot be re-added as new, and Back/Home can be
typed at any prompt to bail out cleanly without a half-filled record
being saved.
"""

from database import run_query, run_insert

LIST_FIELD_HINT = " (comma-separated, e.g. Ventilator 2, IV stand 5)"


class _Nav(Exception):
    def __init__(self, destination):
        self.destination = destination  # "BACK" or "HOME"


def _check_nav(value):
    lowered = value.strip().lower()
    if lowered == "back":
        raise _Nav("BACK")
    if lowered == "home":
        raise _Nav("HOME")


def _read(prompt, allow_empty=False):
    """Base reader: just checks for Back/Home and blank input."""
    while True:
        value = input(prompt).strip()
        _check_nav(value)
        if not value and not allow_empty:
            print("This field cannot be empty. Please try again.")
            continue
        return value


def _read_letters(prompt, allow_empty=False):
    """For patient name, doctor, nurse -- letters and spaces only,
    no digits anywhere in the field."""
    while True:
        value = _read(prompt, allow_empty=allow_empty)
        if not value:
            return value
        if not value.replace(" ", "").isalpha():
            print("This field must contain letters only (no numbers). Please try again.")
            continue
        return value


def _read_starts_with_letter(prompt, allow_empty=False, is_list=False):
    """For illness, equipment, medications, procedures -- each value
    (or each comma-separated item, if is_list=True) must START with a
    letter. Numbers are allowed elsewhere in the text (e.g. 'Ventilator 2'),
    just not as the very first character."""
    while True:
        value = _read(prompt, allow_empty=allow_empty)
        if not value:
            return value
        items = [item.strip() for item in value.split(",")] if is_list else [value]
        items = [item for item in items if item]
        if any(not item[0].isalpha() for item in items):
            print("This field must start with a letter. Please try again.")
            continue
        return value


def _read_digits(prompt, allow_empty=False):
    """For contact and ward number -- digits only."""
    while True:
        value = _read(prompt, allow_empty=allow_empty)
        if not value:
            return value
        if not value.isdigit():
            print("This field must contain numbers only. Please try again.")
            continue
        return value


def _read_positive_int(prompt):
    """For age -- must be a positive whole number."""
    while True:
        value = input(prompt).strip()
        _check_nav(value)
        if value.isdigit() and int(value) > 0:
            return int(value)
        print("Please enter a positive whole number.")


def _read_nonnegative_int(prompt):
    """For number of visits -- 0 is valid (a brand-new patient)."""
    while True:
        value = input(prompt).strip()
        _check_nav(value)
        if value.isdigit():
            return int(value)
        print("Please enter a whole number (0 or more).")


def _read_gender(prompt="Enter gender (M for male & F for female): "):
    while True:
        value = input(prompt).strip()
        _check_nav(value)
        if value.upper() in ("M", "F"):
            return value.upper()
        print("Please enter M or F.")


# -------------------------------------------------------------- Helpers
def patient_name_exists(name):
    rows = run_query("SELECT patient_id FROM patients WHERE name = ?", (name,))
    return len(rows) > 0


def get_patient_by_id(patient_id):
    rows = run_query("SELECT * FROM patients WHERE patient_id = ?", (patient_id,))
    return rows[0] if rows else None


def get_care_details(patient_id):
    rows = run_query("SELECT * FROM care_details WHERE patient_id = ?", (patient_id,))
    return rows[0] if rows else None


# --------------------------------------------------------------- Feature 1
def add_new_patient():
    """Registers a new patient. Rejects duplicates and invalid input."""
    print()
    print("== Add New Patient ==")
    print("(Type Back to go one step Back)")
    print("(Type Home to go back to start)")
    try:
        name = _read_letters("Enter patient name: ")
        if patient_name_exists(name):
            print(f"A patient named '{name}' already exists. "
                  f"Use Search / filter to find their ID instead of "
                  f"adding a duplicate.")
            return None

        illness = _read_starts_with_letter("Enter illness: ", allow_empty=True)
        age = _read_positive_int("Enter age: ")
        gender = _read_gender()
        contact = _read_digits("Enter contact: ", allow_empty=True)
        num_visits = _read_nonnegative_int(
            "Enter number of visits so far (0 if this is their first): "
        )

        new_id = run_insert(
            "INSERT INTO patients (name, age, gender, illness, contact, num_visits) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (name, age, gender, illness, contact, num_visits),
        )
        print(f"New Patient info saved successfully! Assigned Patient ID: {new_id}. "
              f"Returning to the main menu...")
        return None

    except _Nav as nav:
        if nav.destination == "HOME":
            return "HOME"
        print("Cancelled. Returning to the main menu...")
        return None


# --------------------------------------------------------------- Feature 2
def assign_care_details():
    """Assigns or updates a patient's care details."""
    print()
    print("== Assign Care Details ==")
    print("(Type Back to go one step Back)")
    print("(Type Home to go back to start)")
    try:
        pid_str = _read("Enter patient ID: ")
        if not pid_str.isdigit():
            print("Patient ID must be a number.")
            return None
        patient = get_patient_by_id(int(pid_str))
        if not patient:
            print("No patient found with that ID.")
            return None

        print(f"Assigning care details for: {patient['name']} (ID {patient['patient_id']})")
        ward_number = _read_digits("Enter ward number: ")
        doctor = _read_letters("Enter doctor's name: ")
        nurse = _read_letters("Enter nurse's name: ", allow_empty=True)
        equipment = _read_starts_with_letter(
            "Enter equipment used" + LIST_FIELD_HINT + ": ", allow_empty=True, is_list=True
        )
        medications = _read_starts_with_letter(
            "Enter medications" + LIST_FIELD_HINT + ": ", allow_empty=True, is_list=True
        )
        procedures = _read_starts_with_letter(
            "Enter procedures e.g. surgery, catheter insertion"
            + LIST_FIELD_HINT + ": ", allow_empty=True, is_list=True
        )

        existing = get_care_details(patient["patient_id"])
        if existing:
            run_insert(
                "UPDATE care_details SET ward=?, doctor=?, nurse=?, equipment=?, "
                "medications=?, procedures=? WHERE patient_id=?",
                (ward_number, doctor, nurse, equipment, medications, procedures,
                 patient["patient_id"]),
            )
            print("Care details updated successfully! Returning to the main menu...")
        else:
            run_insert(
                "INSERT INTO care_details "
                "(patient_id, ward, doctor, nurse, equipment, medications, procedures) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (patient["patient_id"], ward_number, doctor, nurse, equipment,
                 medications, procedures),
            )
            print("Care details saved successfully! Returning to the main menu...")
        return None

    except _Nav as nav:
        if nav.destination == "HOME":
            return "HOME"
        print("Cancelled. Returning to the main menu...")
        return None


if __name__ == "__main__":
    add_new_patient()
    assign_care_details()
