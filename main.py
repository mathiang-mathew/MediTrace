"""
main.py
-------
Esther Habimana — Features 9-11 & 10: Main Menu, Export & Integration

Wires together everyone else's modules into one numbered CLI menu, handles
global input validation, and provides export_report(). This file assumes the
following already exist (per the task breakdown) and expose these functions:

    patient_registration.py
        add_new_patient()
        assign_care_details()

    logging_functions.py
        log_infection_case()
        log_chw_visit()
        list_followups_due()

    analysis.py
        analyze_hai_patterns()

    search_and_history.py
        view_patient_history(identifier)
        search_filter_by_ward(ward=None, doctor=None)

    database.py
        init_db(), get_connection(), run_query(), run_insert()
"""

import csv
import sys
from datetime import date

import database
import patient_registration
import logging_functions
import analysis
import search_and_history


MENU_TEXT = """
==================================================
 MediTrace — Health Worker CLI
==================================================
 1. Register a new patient
 2. Assign / update care details
 3. Log an infection case
 4. Log a CHW visit
 5. View a patient's full history
 6. List patients due for follow-up
 7. Search / filter by ward or doctor
 8. Analyze HAI patterns
 9. Export a summary report
 0. Exit
--------------------------------------------------
"""


def get_menu_choice():
    """
    Global input validation wrapper: keeps re-prompting on invalid input
    rather than crashing or silently doing nothing.
    """
    while True:
        raw = input("Select an option (0-9): ").strip()
        if raw.isdigit() and 0 <= int(raw) <= 9:
            return int(raw)
        print("Invalid choice — please enter a number from 0 to 9.\n")


def prompt_nonempty(label):
    while True:
        value = input(f"{label}: ").strip()
        if value:
            return value
        print(f"{label} cannot be empty. Please try again.")


def export_report():
    """
    Writes either a single patient's summary or a facility-level HAI summary
    to a text/CSV file, based on the user's choice.
    """
    print("\nExport options:")
    print("  1. Single patient summary (.txt)")
    print("  2. Facility-wide HAI summary (.csv)")
    choice = input("Choose 1 or 2: ").strip()

    if choice == "1":
        pid_or_name = prompt_nonempty("Enter patient ID or name")
        matches = search_and_history._find_patient(pid_or_name)
        if not matches:
            print("No matching patient found — nothing exported.")
            return
        if len(matches) > 1:
            print("Multiple matches found — please re-run export with a patient_id instead.")
            return

        patient = matches[0]
        pid = patient["patient_id"]
        filename = f"patient_{pid}_summary_{date.today().isoformat()}.txt"

        care = database.run_query(
            "SELECT * FROM care_details WHERE patient_id = ?", (pid,)
        )
        infections = database.run_query(
            "SELECT * FROM infections WHERE patient_id = ?", (pid,)
        )
        visits = database.run_query(
            "SELECT * FROM chw_visits WHERE patient_id = ?", (pid,)
        )

        with open(filename, "w") as f:
            f.write(f"MediTrace Patient Summary — {patient['name']} (ID {pid})\n")
            f.write(f"Generated: {date.today().isoformat()}\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Age: {patient['age']}, Gender: {patient['gender']}, "
                    f"Illness: {patient['illness']}, Contact: {patient['contact']}\n\n")

            if care:
                c = care[0]
                f.write("Care Details:\n")
                f.write(f"  Ward: {c['ward']}, Doctor: {c['doctor']}, Nurse: {c['nurse']}\n")
                f.write(f"  Equipment: {c['equipment']}, Medications: {c['medications']}, "
                        f"Procedures: {c['procedures']}\n\n")

            f.write(f"Infection Cases ({len(infections)}):\n")
            for i, row in enumerate(infections, start=1):
                f.write(f"  {i}. {row['infection_type']} — onset {row['date_of_onset']}, "
                        f"Ward {row['ward']}, Equip: {row['equipment']}\n")

            f.write(f"\nCHW Visits ({len(visits)}):\n")
            for i, row in enumerate(visits, start=1):
                f.write(f"  {i}. {row['visit_date']} — {row['reason']} "
                        f"(next follow-up: {row['next_followup_date']})\n")

        print(f"Patient summary exported to {filename}")

    elif choice == "2":
        filename = f"facility_hai_summary_{date.today().isoformat()}.csv"
        rows = database.run_query(
            "SELECT ward, COUNT(*) as case_count FROM infections "
            "GROUP BY ward ORDER BY case_count DESC"
        )
        with open(filename, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Ward", "HAI Case Count"])
            for row in rows:
                writer.writerow([row["ward"], row["case_count"]])
        print(f"Facility HAI summary exported to {filename}")

    else:
        print("Invalid export option — nothing exported.")


def run_menu():
    database.create_tables()

    actions = {
        1: patient_registration.add_new_patient,
        2: patient_registration.assign_care_details,
        3: logging_functions.log_infection_case,
        4: logging_functions.log_chw_visit,
        5: lambda: search_and_history.view_patient_history(
            prompt_nonempty("Enter patient ID or name")
        ),
        6: logging_functions.list_followups_due,
        7: lambda: search_and_history.search_filter_by_ward(
            ward=input("Ward (leave blank to skip): ").strip() or None,
            doctor=input("Doctor (leave blank to skip): ").strip() or None,
        ),
        8: analysis.analyze_hai_patterns,
        9: export_report,
    }

    while True:
        print(MENU_TEXT)
        choice = get_menu_choice()

        if choice == 0:
            print("Goodbye!")
            sys.exit(0)

        action = actions.get(choice)
        try:
            action()
        except Exception as e:
            # Keeps one bad interaction from crashing the whole session.
            print(f"Something went wrong running that option: {e}")

        input("\nPress Enter to return to the menu...")


if __name__ == "__main__":
    run_menu()