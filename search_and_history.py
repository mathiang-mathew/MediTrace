# import database
# import logging_functions

# def view_patient_history():
#     patient_id = ''
#     print(f"{personal details} {care details} {infections} {visits}")
# def search_filter_by_ward():
#     patient_id = ''
#     print(f"{list all patients in given ward} or {all patients under given doctor}")


"""
search_and_history.py
----------------------
Herve Rugwiro — Features 5 & 7: View History, Search/Filter

Owns retrieval and lookup across all four tables (patients, care_details,
infections, chw_visits). Nothing here writes to the database.
"""

from database import run_query


def _find_patient(identifier):
    """
    Resolve a patient by patient_id (int, or numeric string) or by name
    (case-insensitive partial match). Returns the matching patient row(s)
    (as a list, since a name search can match more than one person).
    """
    identifier = str(identifier).strip()

    if identifier.isdigit():
        rows = run_query(
            "SELECT * FROM patients WHERE patient_id = ?", (int(identifier),)
        )
        return rows

    rows = run_query(
        "SELECT * FROM patients WHERE name LIKE ? ORDER BY name",
        (f"%{identifier}%",),
    )
    return rows


def view_patient_history(identifier):
    """
    Takes a patient_id or name, pulls everything across all four tables —
    personal details, care details, infections, visits — and prints one
    readable summary. If a name matches multiple patients, lists them and
    asks the caller to be more specific (e.g. re-search by patient_id).
    """
    matches = _find_patient(identifier)

    if not matches:
        print(f"\nNo patient found matching '{identifier}'.")
        return

    if len(matches) > 1:
        print(f"\nMultiple patients match '{identifier}':")
        for m in matches:
            print(f"  [{m['patient_id']}] {m['name']} (age {m['age']})")
        print("Please search again using the patient_id shown above.")
        return

    patient = matches[0]
    pid = patient["patient_id"]

    print("\n" + "=" * 50)
    print(f" PATIENT HISTORY — {patient['name']} (ID: {pid})")
    print("=" * 50)

    print("\n-- Personal Details --")
    print(f"  Age:        {patient['age']}")
    print(f"  Gender:     {patient['gender']}")
    print(f"  Illness:    {patient['illness']}")
    print(f"  Contact:    {patient['contact']}")
    print(f"  Visits:     {patient['num_visits']}")

    print("\n-- Care Details --")
    care_rows = run_query(
        "SELECT * FROM care_details WHERE patient_id = ?", (pid,)
    )
    if care_rows:
        c = care_rows[0]
        print(f"  Ward:        {c['ward']}")
        print(f"  Doctor:      {c['doctor']}")
        print(f"  Nurse:       {c['nurse']}")
        print(f"  Equipment:   {c['equipment']}")
        print(f"  Medications: {c['medications']}")
        print(f"  Procedures:  {c['procedures']}")
    else:
        print("  No care details assigned yet.")

    print("\n-- Infection Cases --")
    infection_rows = run_query(
        "SELECT * FROM infections WHERE patient_id = ? ORDER BY date_of_onset",
        (pid,),
    )
    if infection_rows:
        for i, row in enumerate(infection_rows, start=1):
            print(f"  {i}. {row['infection_type']} (onset {row['date_of_onset']}) "
                  f"— Ward {row['ward']}, Dr. {row['doctor']}, Equip: {row['equipment']}")
    else:
        print("  No infection cases logged.")

    print("\n-- CHW Visits --")
    visit_rows = run_query(
        "SELECT * FROM chw_visits WHERE patient_id = ? ORDER BY visit_date",
        (pid,),
    )
    if visit_rows:
        for i, row in enumerate(visit_rows, start=1):
            print(f"  {i}. {row['visit_date']} — {row['reason']} "
                  f"(next follow-up: {row['next_followup_date']})")
    else:
        print("  No CHW visits logged.")

    print("=" * 50 + "\n")


def search_filter_by_ward(ward=None, doctor=None):
    """
    Lists all patients in a given ward, and/or all patients under a given
    doctor. At least one of ward/doctor should be provided; if both are
    given, results must match both.
    """
    if not ward and not doctor:
        print("Please provide a ward and/or a doctor name to search by.")
        return []

    query = (
        "SELECT p.patient_id, p.name, c.ward, c.doctor "
        "FROM patients p JOIN care_details c ON p.patient_id = c.patient_id "
        "WHERE 1=1"
    )
    params = []
    if ward:
        query += " AND c.ward LIKE ?"
        params.append(f"%{ward}%")
    if doctor:
        query += " AND c.doctor LIKE ?"
        params.append(f"%{doctor}%")
    query += " ORDER BY c.ward, p.name"

    rows = run_query(query, tuple(params))

    label_bits = []
    if ward:
        label_bits.append(f"ward '{ward}'")
    if doctor:
        label_bits.append(f"doctor '{doctor}'")
    label = " and ".join(label_bits)

    if not rows:
        print(f"\nNo patients found for {label}.")
        return []

    print(f"\nPatients matching {label}:")
    for r in rows:
        print(f"  [{r['patient_id']}] {r['name']} — Ward {r['ward']}, Dr. {r['doctor']}")

    return rows


if __name__ == "__main__":
    # Quick manual test against database.seed_sample_data()
    import database
    database.seed_sample_data()

    view_patient_history(1)
    view_patient_history("Niyonzima")
    search_filter_by_ward(ward="Ward 4b")
    search_filter_by_ward(doctor="Habimana")