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

Validation rules, field by field:
    - patient name, doctor, nurse    -> letters only, required
    - illness                        -> chosen from a fixed list of
                                         common illnesses/infections,
                                         with an "Other" option to type
                                         a free-text value (must start
                                         with a letter)
    - equipment, medications,
      procedures                     -> required, must START with a
                                         letter (each comma-separated
                                         item checked individually for
                                         the list fields)
    - age                            -> required, positive whole number
    - number of visits               -> required, whole number, 0 or more
    - gender                         -> required, M or F only
    - contact                        -> required, exactly 10 digits,
                                         optionally preceded by a '+'
                                         and a 1-3 digit country code
                                         (e.g. 0788123456 or +250788123456).
                                         If a country code is typed it is
                                         validated as part of the same
                                         pattern -- it isn't just tacked
                                         on and ignored.
    - ward                           -> required, AND must match a ward
                                         that already exists somewhere in
                                         the database (care_details or
                                         infections) -- unless the
                                         database has no ward on file at
                                         all yet, in which case the first
                                         ward entered becomes the first
                                         valid one on file. Wards in
                                         MediTrace are not purely numeric
                                         (e.g. "1a", "ICU", "Maternity"),
                                         so this is a lookup against real
                                         values, not a digits-only check.

No field anywhere accepts a blank answer -- every single prompt in this
module (including numeric and single-letter ones) is funneled through
_read_raw() first, which enforces that. Back/Home can also be typed at
ANY prompt to bail out cleanly without a half-filled record being
saved -- every prompt below shows the Back/Home hint and checks for it
before validating anything else.
"""

import re

from database import run_query, run_insert

LIST_FIELD_HINT = " (comma-separated, e.g. Ventilator 2, IV stand 5)"
NAV_HINT = " [Back/Home]: "

# Optional "+" and 1-3 digit country code, followed by exactly 10 digits.
# Matches: 0788123456  |  +250788123456  |  +1XXXXXXXXXX (no spaces allowed)
CONTACT_PATTERN = re.compile(r"^(\+\d{1,3})?\d{10}$")

# Fixed pick-list for the illness field on Feature 1. Covers the illnesses
# and healthcare-associated infections MediTrace already tracks, plus an
# "Other" escape hatch for anything not on the list.
ILLNESS_OPTIONS = [
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


class _Nav(Exception):
    def __init__(self, destination):
        self.destination = destination  # "BACK" or "HOME"


def _check_nav(value):
    lowered = value.strip().lower()
    if lowered == "back":
        raise _Nav("BACK")
    if lowered == "home":
        raise _Nav("HOME")


# -------------------------------------------------------------- Base reader
def _read_raw(prompt):
    """The single foundation every field reader in this module goes
    through: checks for Back/Home, and refuses to accept a blank
    answer. No field in MediTrace's patient registration is optional,
    and no field is exempt from Back/Home navigation -- including the
    numeric and single-letter ones, which used to call input()
    directly and are now routed through here too."""
    while True:
        value = input(prompt).strip()
        _check_nav(value)
        if not value:
            print("This field cannot be empty. Please try again.")
            continue
        return value


# -------------------------------------------------------------- Validators
def _read_letters(prompt):
    """For patient name, doctor, nurse -- letters and spaces only."""
    while True:
        value = _read_raw(prompt)
        if not value.replace(" ", "").isalpha():
            print("This field must contain letters only (no numbers). Please try again.")
            continue
        return value


def _read_starts_with_letter(prompt, is_list=False):
    """For equipment, medications, procedures (and free-text illness)
    -- each value (or each comma-separated item, if is_list=True) must
    START with a letter. Digits are fine elsewhere in the text (e.g.
    'Ventilator 2'), just not as the very first character."""
    while True:
        value = _read_raw(prompt)
        items = [item.strip() for item in value.split(",")] if is_list else [value]
        items = [item for item in items if item]
        if not items or any(not item[0].isalpha() for item in items):
            print("This field must start with a letter. Please try again.")
            continue
        return value


def _read_positive_int(prompt):
    """For age -- must be a positive whole number."""
    while True:
        value = _read_raw(prompt)
        if value.isdigit() and int(value) > 0:
            return int(value)
        print("Please enter a positive whole number.")


def _read_nonnegative_int(prompt):
    """For number of visits -- 0 is a valid answer, blank is not."""
    while True:
        value = _read_raw(prompt)
        if value.isdigit():
            return int(value)
        print("Please enter a whole number (0 or more).")


def _read_gender(prompt="Enter gender (M for male & F for female)" + NAV_HINT):
    while True:
        value = _read_raw(prompt)
        if value.upper() in ("M", "F"):
            return value.upper()
        print("Please enter M or F.")


def _read_contact(prompt):
    """Exactly 10 digits, with an optional '+' and country code in
    front (e.g. 0788123456, or +250788123456). If a country code is
    supplied it's validated as part of the same pattern -- a stray
    '+' or a code of the wrong length is rejected, not silently
    accepted."""
    while True:
        value = _read_raw(prompt)
        if not CONTACT_PATTERN.match(value):
            print("Contact must be exactly 10 digits (a '+' and a 1-3 digit "
                  "country code may optionally come before them, e.g. "
                  "+250788123456). Please try again.")
            continue
        return value


def _read_illness(prompt_intro="Select the patient's illness/infection:"):
    """Presents the fixed illness pick-list plus an 'Other' option
    that falls back to free text (must start with a letter)."""
    other_num = len(ILLNESS_OPTIONS) + 1
    while True:
        print(prompt_intro)
        for i, name in enumerate(ILLNESS_OPTIONS, start=1):
            print(f"  {i}. {name}")
        print(f"  {other_num}. Other (please specify)")
        choice = _read_raw(f"Enter a number 1-{other_num}" + NAV_HINT)
        if not choice.isdigit():
            print(f"Please enter a number between 1 and {other_num}.")
            continue
        choice_num = int(choice)
        if 1 <= choice_num <= len(ILLNESS_OPTIONS):
            return ILLNESS_OPTIONS[choice_num - 1]
        if choice_num == other_num:
            return _read_starts_with_letter("Enter the illness/infection name" + NAV_HINT)
        print(f"Please enter a number between 1 and {other_num}.")


def _read_ward(prompt):
    """Required, and must match a ward that already exists somewhere
    in the database (care_details or infections) -- unless no ward
    has ever been recorded anywhere yet, in which case whatever is
    entered becomes the first valid one on file. Wards are matched
    case-insensitively and normalized to the exact spelling already on
    file (so 'icu' and 'ICU' don't end up as two different wards)."""
    existing = get_existing_wards()
    if existing:
        print("Existing wards on file: " + ", ".join(existing))
    while True:
        value = _read_raw(prompt)
        if not existing:
            return value
        match = next((w for w in existing if w.lower() == value.lower()), None)
        if match is None:
            print(f"'{value}' is not a ward on file. "
                  f"Please enter one of: {', '.join(existing)}.")
            continue
        return match


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


def get_existing_wards():
    """Distinct wards already recorded anywhere in the database --
    checks both care_details and infections, since either one may
    have wards the other doesn't. Blank/NULL values are ignored so
    they can never become a bogus 'valid' ward."""
    rows_care = run_query(
        "SELECT DISTINCT ward FROM care_details "
        "WHERE ward IS NOT NULL AND TRIM(ward) != ''"
    )
    rows_inf = run_query(
        "SELECT DISTINCT ward FROM infections "
        "WHERE ward IS NOT NULL AND TRIM(ward) != ''"
    )
    wards = {row["ward"] for row in rows_care} | {row["ward"] for row in rows_inf}
    return sorted(wards)


# --------------------------------------------------------------- Feature 1
def add_new_patient():
    """Registers a new patient. Rejects duplicates and invalid input."""
    print()
    print("== Add New Patient ==")
    print("(Type Back to go one step Back)")
    print("(Type Home to go back to start)")
    try:
        name = _read_letters("Enter patient name" + NAV_HINT)
        if patient_name_exists(name):
            print(f"A patient named '{name}' already exists. "
                  f"Use Search / filter to find their ID instead of "
                  f"adding a duplicate.")
            return None

        illness = _read_illness()
        age = _read_positive_int("Enter age" + NAV_HINT)
        gender = _read_gender()
        contact = _read_contact("Enter contact (10 digits, e.g. 0788123456)" + NAV_HINT)
        num_visits = _read_nonnegative_int(
            "Enter number of visits so far (0 if this is their first)" + NAV_HINT
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
        pid_str = _read_raw("Enter patient ID" + NAV_HINT)
        if not pid_str.isdigit():
            print("Patient ID must be a number.")
            return None
        patient = get_patient_by_id(int(pid_str))
        if not patient:
            print("No patient found with that ID.")
            return None

        print(f"Assigning care details for: {patient['name']} (ID {patient['patient_id']})")
        ward = _read_ward("Enter ward" + NAV_HINT)
        doctor = _read_letters("Enter doctor's name" + NAV_HINT)
        nurse = _read_letters("Enter nurse's name" + NAV_HINT)
        equipment = _read_starts_with_letter(
            "Enter equipment used" + LIST_FIELD_HINT + NAV_HINT, is_list=True
        )
        medications = _read_starts_with_letter(
            "Enter medications" + LIST_FIELD_HINT + NAV_HINT, is_list=True
        )
        procedures = _read_starts_with_letter(
            "Enter procedures e.g. surgery, catheter insertion" + LIST_FIELD_HINT + NAV_HINT,
            is_list=True,
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
