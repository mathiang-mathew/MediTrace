
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
number, and Back/Home can be typed at any prompt to bail out cleanly
without a half-filled record being saved.
"""

from database import run_query, run_insert

# equipment/medications/procedures are stored as comma-separated text in
# care_details (see analysis.py's LIST_COLUMNS) -- this hint keeps data
# entry consistent with how Kabi's analysis module expects to split it.
LIST_FIELD_HINT = " (comma-separated, e.g. Ventilator 2, IV stand 5)"


class _Nav(Exception):
    """Raised when the user types Back or Home mid-entry, so a
    half-filled registration or care update never gets partially saved."""
    def __init__(self, destination):
        self.destination = destination  # "BACK" or "HOME"


def _check_nav(value):
    lowered = value.strip().lower()
    if lowered == "back":
        raise _Nav("BACK")
    if lowered == "home":
        raise _Nav("HOME")


def _read(prompt, allow_empty=False):
    """Read one text field. Rejects blank input unless allow_empty=True."""
    while True:
        value = input(prompt).strip()
        _check_nav(value)
        if not value and not allow_empty:
            print("This field cannot be empty. Please try again.")
            continue
        return value


def _read_nonnegative_int(prompt):
    """Used for number of visits -- 0 is valid (a brand-new patient)."""
    while True:
        value = input(prompt).strip()
        _check_nav(value)
        if value.isdigit():
            return int(value)
        print("Please enter a whole number (0 or more).")


def _read_positive_int(prompt):
    """Used for age -- the schema enforces age > 0, so we check it here too
    to give a friendly message instead of a raw SQLite error."""
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


# -------------------------------------------------------------- Helpers
def patient_name_exists(name):
    """True if a patient with this exact name is already registered."""
    rows = run_query("SELECT patient_id FROM patients WHERE name = ?", (name,))
    return len(rows) > 0


def get_patient_by_id(patient_id):
    """Returns the patient row, or None if no such ID exists."""
    rows = run_query(
        "SELECT * FROM patients WHERE patient_id = ?", (patient_id,)
    )
    return rows[0] if rows else None


def get_care_details(patient_id):
    """Returns the patient's current care_details row, or None."""
    rows = run_query(
        "SELECT * FROM care_details WHERE patient_id = ?", (patient_id,)
    )
    return rows[0] if rows else None


# --------------------------------------------------------------- Feature 1
def add_new_patient():
    """Registers a new patient. Rejects duplicates and invalid input.
    Prints the assigned patient ID so the worker can use it immediately
    for Feature 2 (assign care details)."""
    print()
    print("== Add New Patient ==")
    print("(Type Back to go one step Back)")
    print("(Type Home to go back to start)")
    try:
        name = _read("Enter patient name: ")
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


# --------------------------------------------------------------- Feature 2
def assign_care_details():
    """Assigns or updates a patient's care details. Looks up the
    patient by ID first, then inserts a new care_details row or
    updates the existing one -- care can change over time, so this
    must never create a second row for the same patient."""
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
        doctor = _read("Enter doctor's name: ")
        nurse = _read("Enter nurse's name: ", allow_empty=True)
        equipment = _read("Enter equipment used" + LIST_FIELD_HINT + ": ", allow_empty=True)
        medications = _read("Enter medications" + LIST_FIELD_HINT + ": ", allow_empty=True)
        procedures = _read(
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
    # Lets this module be run on its own for testing, without main.py.
    add_new_patient()
    assign_care_details()
