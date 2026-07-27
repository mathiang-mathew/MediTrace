"""
patient_registration.py
-------------------------
Features 1-2 of MediTrace: patient registration and care assignment.
Owner: Benigne Akayesu Ingabire

Entry points for main.py:
    from patient_registration import add_new_patient, assign_care_details
    result = add_new_patient()
    result = assign_care_details()

Both return "HOME" if the user typed Home to jump back to the start of
the program, or None otherwise -- the same convention analysis.py uses
for analyze_hai_patterns(), so main.py can handle both the same way.

Validation follows Feature 11 of the spec: empty names are rejected, an
existing patient cannot be re-added as new, age must be a positive
number, Back/Home can be typed at any prompt to bail out cleanly, and
name-like fields (patient name, doctor, nurse, medications, procedures)
must contain letters rather than being purely numeric.
"""

from database import run_query, run_insert

LIST_FIELD_HINT = " (comma-separated, e.g. Ventilator 2, IV stand 5)"


class _Nav(Exception):
    def __init__(self, destination):
        self.destination = destination


def _check_nav(value):
    lowered = value.strip().lower()
    if lowered == "back":
        raise _Nav("BACK")
    if lowered == "home":
        raise _Nav("HOME")


def _read(prompt, allow_empty=False):
    while True:
        value = input(prompt).strip()
        _check_nav(value)
        if not value and not allow_empty:
            print("This field cannot be empty. Please try again.")
            continue
        return value


def _read_alpha(prompt, allow_empty=False):
    while True:
        value = _read(prompt, allow_empty=allow_empty)
        if not value:
            return value
        items = [item.strip() for item in value.split(",") if item.strip()]
        if any(item.replace(" ", "").isdigit() for item in items):
            print("This field must contain letters, not just numbers. Please try again.")
            continue
        return value


def _read_nonnegative_int(prompt):
    while True:
        value = input(prompt).strip()
        _check_nav(value)
        if value.isdigit():
            return int(value)
        print("Please enter a whole number (0 or more).")


def _read_positive_int(prompt):
    while True:
        value = input(prompt).strip()
        _check_nav(value)
        if value.isdigit() and int(value) > 0:
            return int(value)
        print("Please enter a positive whole number.")


def _read_gender(prompt="Enter gender (M for male & F for female): "):
    while True:
        value = input(prompt).strip()
        _check_nav(value)
        if value.upper() in ("M", "F"):
            return value.upper()
        print("Please enter M or F.")


def patient_name_exists(name):
    rows = run_query("SELECT patient_id FROM patients WHERE name = ?", (name,))
    return len(rows) > 0


def get_patient_by_id(patient_id):
    rows = run_query("SELECT * FROM patients WHERE patient_id = ?", (patient_id,))
    return rows[0] if rows else None


def get_care_details(patient_id):
    rows = run_query("SELECT * FROM care_details WHERE patient_id = ?", (patient_id,))
    return rows[0] if rows else None


def add_new_patient():
    print()
    print("== Add New Patient ==")
    print("(Type Back to go one step Back)")
    print("(Type Home to go back to start)")
    try:
        name = _read_alpha("Enter patient name: ")
        if patient_name_exists(name):
            print(f"A patient named '{name}' already exists. "
                  f"Use Search / filter to find their ID instead of "
                  f"adding a duplicate.")
            return None

        illness = _read("Enter illness: ", allow_empty=True)
        age = _read_positive_int("Enter age: ")
        gender = _read_gender()
        contact = _read("Enter contact: ", allow_empty=True)
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


def assign_care_details():
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
        ward = _read("Enter ward: ")
        doctor = _read_alpha("Enter doctor's name: ")
        nurse = _read_alpha("Enter nurse's name: ", allow_empty=True)
        equipment = _read("Enter equipment used" + LIST_FIELD_HINT + ": ", allow_empty=True)
        medications = _read_alpha("Enter medications" + LIST_FIELD_HINT + ": ", allow_empty=True)
        procedures = _read_alpha(
            "Enter procedures e.g. surgery, catheter insertion"
            + LIST_FIELD_HINT + ": ", allow_empty=True
        )

        existing = get_care_details(patient["patient_id"])
        if existing:
            run_insert(
                "UPDATE care_details SET ward=?, doctor=?, nurse=?, equipment=?, "
                "medications=?, procedures=? WHERE patient_id=?",
                (ward, doctor, nurse, equipment, medications, procedures,
                 patient["patient_id"]),
            )
            print("Care details updated successfully! Returning to the main menu...")
        else:
            run_insert(
                "INSERT INTO care_details "
                "(patient_id, ward, doctor, nurse, equipment, medications, procedures) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (patient["patient_id"], ward, doctor, nurse, equipment,
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
