"""
seed_data.py
-------------
Generates a realistic dummy dataset for MediTrace so every teammate can
build and test their feature against real-looking data instead of an
empty database. No real patient data is used anywhere, per the project's
design constraints.

Run it directly:
    python3 seed_data.py

Safe to re-run: it wipes and rebuilds the four tables each time, so
nobody accumulates duplicate test data. The random seed is fixed, so
everyone on the team gets the exact same "random" dataset.
"""

import random
from datetime import datetime, timedelta

from database import create_tables, get_connection, run_insert

random.seed(42)

FIRST_NAMES = [
    "David", "Grace", "Peter", "Mary", "John", "Esther", "Emmanuel", "Diane",
    "Elias", "Sarah", "Moses", "Agnes", "Samuel", "Joyce", "Daniel", "Ruth",
    "Isaac", "Florence", "Patrick", "Immaculee", "James", "Winnie", "Vincent",
    "Christine", "Robert",
]
LAST_NAMES = [
    "Boyo", "Uwimana", "Otieno", "Achieng", "Niyonzima", "Mbabazi", "Habimana",
    "Ingabire", "Mayom", "Deng", "Nyandeng", "Garang", "Akol", "Wani", "Lino",
    "Chol", "Bol", "Kelvin", "Musa", "Noel",
]

WARDS = ["1a", "1b", "2a", "2b", "3a", "3b", "4a", "4b", "ICU", "Maternity"]
# Ward "4b" is weighted higher below so pattern analysis has an obvious
# "worst ward" to surface later, similar to the spec's own example table.
WARD_WEIGHTS = [2, 2, 2, 2, 4, 2, 3, 16, 3, 2]

DOCTORS = [
    "Dr. Hussain Kelvin", "Dr. Hervin Musa", "Dr. Faith Noel",
    "Dr. Sarah Achieng", "Dr. Peter Otieno", "Dr. Grace Uwimana",
]
NURSES = [
    "Nurse Alice Mbabazi", "Nurse John Niyonzima", "Nurse Betty Umutesi",
    "Nurse Emmanuel Habiyaremye", "Nurse Diane Ingabire",
]
EQUIPMENT = [
    "Ventilator 1", "Ventilator 2", "Catheter set A", "Catheter set B",
    "IV stand 3", "IV stand 5", "Dialysis machine", "Oxygen concentrator",
]
MEDICATIONS = [
    "Amoxicillin", "Ceftriaxone", "Paracetamol", "Metronidazole",
    "Ibuprofen", "Vancomycin",
]
PROCEDURES = [
    "Laparotomy", "Wound dressing", "Intermittent catheter insertion",
    "Appendectomy", "C-section", "Physiotherapy session",
]
ILLNESSES = [
    "Malaria", "Typhoid", "Pneumonia", "Hypertension",
    "Diabetes complications", "Road traffic accident injury",
    "Postpartum care", "Tuberculosis",
]
INFECTION_TYPES = [
    "Surgical site infection", "Catheter-associated UTI",
    "Ventilator-associated pneumonia", "Bloodstream infection",
    "Central line-associated infection",
]
CHW_REASONS = [
    "Routine check-up", "Medication follow-up", "Wound check",
    "Vaccination visit", "Postnatal check", "Blood pressure monitoring",
]

NUM_PATIENTS = 28
TODAY = datetime.now()


def random_date(days_back_min, days_back_max):
    """A date between days_back_max and days_back_min days ago.
    Pass a negative days_back_min to allow dates in the future."""
    days_back = random.randint(days_back_min, days_back_max)
    return (TODAY - timedelta(days=days_back)).strftime("%Y-%m-%d")


def weighted_equipment_list():
    """1-2 random equipment items, with Ventilator 2 boosted so it shows
    up disproportionately among infected patients (matches the spec's
    illustrative HAI-by-equipment example)."""
    items = random.sample(EQUIPMENT, k=random.randint(1, 2))
    if random.random() < 0.35 and "Ventilator 2" not in items:
        items.append("Ventilator 2")
    return items


def seed():
    create_tables()

    conn = get_connection()
    conn.execute("DELETE FROM infections")
    conn.execute("DELETE FROM chw_visits")
    conn.execute("DELETE FROM care_details")
    conn.execute("DELETE FROM patients")
    conn.commit()
    conn.close()

    for _ in range(NUM_PATIENTS):
        name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        age = random.randint(1, 85)
        gender = random.choice(["M", "F"])
        illness = random.choice(ILLNESSES)
        contact = f"0{random.randint(700000000, 799999999)}"
        num_visits = random.randint(1, 6)

        patient_id = run_insert(
            "INSERT INTO patients (name, age, gender, illness, contact, num_visits) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (name, age, gender, illness, contact, num_visits),
        )

        ward = random.choices(WARDS, weights=WARD_WEIGHTS, k=1)[0]
        doctor = random.choice(DOCTORS)
        nurse = random.choice(NURSES)
        equipment = ", ".join(weighted_equipment_list())
        medications = ", ".join(random.sample(MEDICATIONS, k=random.randint(1, 2)))
        procedures = ", ".join(random.sample(PROCEDURES, k=random.randint(1, 2)))

        run_insert(
            "INSERT INTO care_details "
            "(patient_id, ward, doctor, nurse, equipment, medications, procedures) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (patient_id, ward, doctor, nurse, equipment, medications, procedures),
        )

        # ~45% of patients get a logged HAI case -- enough volume for the
        # analysis feature to produce a meaningful ranked result
        if random.random() < 0.45:
            infection_type = random.choice(INFECTION_TYPES)
            date_of_onset = random_date(2, 120)
            run_insert(
                "INSERT INTO infections "
                "(patient_id, infection_type, date_of_onset, ward, doctor, nurse, "
                "equipment, medications, procedures) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (patient_id, infection_type, date_of_onset, ward, doctor, nurse,
                 equipment, medications, procedures),
            )

        # 0-3 CHW visits per patient. next_followup_date is calculated
        # relative to that visit's own date (a few days to a few weeks
        # later) rather than picked independently, so it can never land
        # before the visit happened. Some still end up overdue and some
        # upcoming relative to today, so Feature 6 has real cases to find.
        for _ in range(random.randint(0, 3)):
            visit_dt = TODAY - timedelta(days=random.randint(1, 60))
            followup_dt = visit_dt + timedelta(days=random.randint(3, 45))
            reason = random.choice(CHW_REASONS)
            run_insert(
                "INSERT INTO chw_visits "
                "(patient_id, visit_date, reason, notes, next_followup_date) "
                "VALUES (?, ?, ?, ?, ?)",
                (patient_id, visit_dt.strftime("%Y-%m-%d"), reason,
                 "Routine notes.", followup_dt.strftime("%Y-%m-%d")),
            )

    print(f"Seeded {NUM_PATIENTS} patients with care details, infections, and CHW visits.")


if __name__ == "__main__":
    seed()
