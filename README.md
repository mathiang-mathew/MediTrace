# MediTrace
Python + SQLite CLI for patient records and HAI source-tracking

We built the shared database layer first. Created the SQLite schema (patients, care_details, infections, chw_visits) and the shared helper functions (get_connection, run_query, run_insert) that every other module would build against, then generated dummy sample data - [Mathiang]

Built each functional module in parallel, all working with the same shared schema and sample dataset (dummy data):
    Patient registration and care assignment - [Benigne]
    Infection and CHW visit logging (linked back to existing care details) - [Elnathan]
    Search and full patient history lookups - [Herve]
    HAI pattern analysis (grouped counts by doctor, ward, equipment) - [Kabi]
    
    
Built the main menu and integration layer — the numbered CLI loop, global input validation, and the export function — wiring all the modules together into one program - [Esther]
