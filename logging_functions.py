"""
logging_functions.py
Features 3, 4 and 6 — infection case logging, CHW visit logging,
and listing patients due for follow-up.

Author: Elnathan Mulugeta
"""

from datetime import date, datetime
from database import run_query, run_insert

def prompt_nonempty(label):
    """Keep asking until the user types something that isn't blank."""
    while True:
        value = input(label).strip()
        if value:
            return value
        print("This field cannot be empty. Please try again.")


def prompt_date(label):
    """Keep asking until the user types a valid YYYY-MM-DD date."""
    while True:
        value = input(label).strip()
        try:
            datetime.strptime(value, "%Y-%m-%d")
            return value
        except ValueError:
            print("Invalid date. Use YYYY-MM-DD, e.g. 2026-07-26.")


def get_patient(patient_id):
    """Return the patient's row, or None if no patient has that ID."""
    rows = run_query("SELECT * FROM patients WHERE patient_id = ?", (patient_id,))
    return rows[0] if rows else None

def log_infection_case():
    """Feature 3 — log an HAI case, auto-linking the patient's care details."""

    # 1. Ask for the patient and check they exist
    raw = input("Enter patient ID: ").strip()
    if not raw.isdigit():
        print("Patient ID must be a number.")
        return

    patient = get_patient(int(raw))
    if patient is None:
        print(f"No patient found with ID {raw}.")
        return

    # 2. Pull their current care details
    care_rows = run_query(
        "SELECT * FROM care_details WHERE patient_id = ?", (patient["patient_id"],)
    )
    if not care_rows:
        print(f"{patient['name']} has no care details yet.")
        print("Assign care details first (menu option 2).")
        return
    care = care_rows[0]

    # 3. Ask only for what the system can't work out itself
    print(f"\nLogging infection for: {patient['name']}")
    print(f"Auto-linked ward: {care['ward']}  |  doctor: {care['doctor']}")

    infection_type = prompt_nonempty("Enter infection type: ")
    onset = prompt_date("Enter date of onset (YYYY-MM-DD): ")

    # 4. Save, copying the care details into the infection record
    run_insert(
        """INSERT INTO infections
           (patient_id, infection_type, date_of_onset,
            ward, doctor, nurse, equipment, medications, procedures)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (patient["patient_id"], infection_type, onset,
         care["ward"], care["doctor"], care["nurse"],
         care["equipment"], care["medications"], care["procedures"]),
    )

    # 5. Show what was linked automatically
    print("\nInfection case logged successfully.")
    print(f"  Ward:       {care['ward']}")
    print(f"  Doctor:     {care['doctor']}")
    print(f"  Equipment:  {care['equipment']}")
    print(f"  Procedures: {care['procedures']}")