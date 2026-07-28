"""
logging_functions.py
Features 3, 4 and 6 — infection case logging, CHW visit logging,
and listing patients due for follow-up.

Author: Elnathan Mulugeta
"""

from datetime import date, datetime
from database import run_query, run_insert


class LoggingService:
    """Handles the three logging features and the validation they share.

    Infection logging, CHW visit logging and follow-up listing all need the
    same input checks — a real patient, a valid date, descriptive text.
    Grouping them in one class keeps that validation with the features that
    use it instead of leaving it as loose functions.
    """

    # ---------- shared input validation ----------

    @staticmethod
    def prompt_nonempty(label):
        """Keep asking until the user types text containing at least one letter."""
        while True:
            value = input(label).strip()

            if not value:
                print("This field cannot be empty. Please try again.")
                continue

            if not any(char.isalpha() for char in value):
                print("This field must contain letters, not just numbers. Please try again.")
                continue

            return value

    @staticmethod
    def prompt_date(label):
        """Keep asking until the user types a valid YYYY-MM-DD date."""
        while True:
            value = input(label).strip()
            try:
                datetime.strptime(value, "%Y-%m-%d")
                return value
            except ValueError:
                print("Invalid date. Use YYYY-MM-DD, e.g. 2026-07-26.")

    @staticmethod
    def get_patient(patient_id):
        """Return the patient's row, or None if no patient has that ID."""
        rows = run_query("SELECT * FROM patients WHERE patient_id = ?", (patient_id,))
        return rows[0] if rows else None

    def prompt_patient(self):
        """Keep asking for a patient ID until a real patient is found.

        Returns the patient's row, or None if the user types 'back'.
        """
        while True:
            raw = input("Enter patient ID (or 'back' to return to the menu): ").strip()

            if raw.lower() in ("back", "b"):
                return None

            if not raw.isdigit():
                print("Patient ID must be a number. Please try again.")
                continue

            patient = self.get_patient(int(raw))
            if patient is None:
                print(f"No patient found with ID {raw}. Please try again.")
                continue

            return patient

    # ---------- Feature 3 ----------

    def log_infection_case(self):
        """Log an HAI case, auto-linking the patient's care details."""

        # 1. Ask for the patient and check they exist
        patient = self.prompt_patient()
        if patient is None:
            return

        # 2. Pull their current care details
        care_rows = run_query(
            "SELECT * FROM care_details WHERE patient_id = ?", (patient["patient_id"],)
        )
        if not care_rows:
            print(f"{patient['name']} has no care details yet.")
            print("Assign care details for this patient first.")
            return
        care = care_rows[0]

        # 3. Ask only for what the system can't work out itself
        print(f"\nLogging infection for: {patient['name']}")
        print(f"Auto-linked ward: {care['ward']}  |  doctor: {care['doctor']}")

        infection_type = self.prompt_nonempty("Enter infection type: ")
        onset = self.prompt_date("Enter date of onset (YYYY-MM-DD): ")

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

        # 5. Show the full record, separating typed from auto-linked
        print("\nInfection case logged successfully.")
        print(f"  Patient:        {patient['name']} (ID {patient['patient_id']})")
        print(f"  Infection type: {infection_type}")
        print(f"  Date of onset:  {onset}")
        print("  --- auto-linked from the patient's care record ---")
        print(f"  Ward:           {care['ward']}")
        print(f"  Doctor:         {care['doctor']}")
        print(f"  Nurse:          {care['nurse']}")
        print(f"  Equipment:      {care['equipment']}")
        print(f"  Medications:    {care['medications']}")
        print(f"  Procedures:     {care['procedures']}")

    # ---------- Feature 4 ----------

    def log_chw_visit(self):
        """Log a community health worker visit and set the next follow-up."""

        # 1. Same patient check
        patient = self.prompt_patient()
        if patient is None:
            return

        # 2. Collect the visit details
        print(f"\nLogging CHW visit for: {patient['name']}")

        visit_date = self.prompt_date("Enter visit date (YYYY-MM-DD): ")
        reason = self.prompt_nonempty("Enter reason for visit: ")
        notes = input("Enter notes (optional, press Enter to skip): ").strip()

        # 3. A follow-up before the visit is a data-entry error
        while True:
            followup = self.prompt_date("Enter next follow-up date (YYYY-MM-DD): ")
            if followup >= visit_date:
                break
            print("The follow-up date cannot be before the visit date.")

        # 4. Save the visit
        run_insert(
            """INSERT INTO chw_visits
               (patient_id, visit_date, reason, notes, next_followup_date)
               VALUES (?, ?, ?, ?, ?)""",
            (patient["patient_id"], visit_date, reason, notes, followup),
        )

        # 5. Keep the patient's visit count in step
        run_insert(
            "UPDATE patients SET num_visits = num_visits + 1 WHERE patient_id = ?",
            (patient["patient_id"],),
        )

        print(f"\nVisit logged for {patient['name']}.")
        print(f"  Next follow-up: {followup}")

    # ---------- Feature 6 ----------

    def list_followups_due(self):
        """List patients whose follow-up is due today or already overdue."""

        # 1. Today, in the same text format the database uses
        today = date.today().isoformat()

        # 2. JOIN because the dates are in chw_visits but the names are in patients
        rows = run_query(
            """SELECT p.patient_id, p.name, p.contact,
                      v.next_followup_date, v.reason
               FROM chw_visits v
               JOIN patients p ON p.patient_id = v.patient_id
               WHERE v.next_followup_date IS NOT NULL
                 AND v.next_followup_date <= ?
               ORDER BY v.next_followup_date ASC""",
            (today,),
        )

        if not rows:
            print("\nNo patients are due for follow-up today.")
            return

        # 3. Print as a table
        print(f"\nPatients due for follow-up (as of {today})")
        print("-" * 70)
        print(f"{'ID':<5}{'Name':<22}{'Due date':<14}{'Status':<12}{'Reason'}")
        print("-" * 70)

        for row in rows:
            status = "OVERDUE" if row["next_followup_date"] < today else "Due today"
            print(f"{row['patient_id']:<5}{row['name']:<22}"
                  f"{row['next_followup_date']:<14}{status:<12}{row['reason']}")

        print("-" * 70)
        print(f"{len(rows)} follow-up(s) due.")


# ---------------------------------------------------------------------------
# Module-level wrappers.
# main.py calls logging_functions.log_infection_case() and friends, so these
# keep that interface working while the logic lives in the class above.
# ---------------------------------------------------------------------------

_service = LoggingService()


def log_infection_case():
    """Feature 3 — see LoggingService.log_infection_case."""
    _service.log_infection_case()


def log_chw_visit():
    """Feature 4 — see LoggingService.log_chw_visit."""
    _service.log_chw_visit()


def list_followups_due():
    """Feature 6 — see LoggingService.list_followups_due."""
    _service.list_followups_due()


if __name__ == "__main__":
    # Standalone test menu. main.py calls the wrapper functions directly.
    while True:
        print("\n--- MediTrace: Logging Module ---")
        print("1. Log infection case")
        print("2. Log CHW visit")
        print("3. List follow-ups due")
        print("0. Back")
        choice = input("Choice: ").strip()

        if choice == "1":
            log_infection_case()
        elif choice == "2":
            log_chw_visit()
        elif choice == "3":
            list_followups_due()
        elif choice == "0":
            break
        else:
            print("Invalid choice. Please enter 0-3.")