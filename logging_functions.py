"""
logging_functions.py
Features 3, 4 and 6 — infection case logging, CHW visit logging,
and listing patients due for follow-up.

Author: Elnathan Mulugeta
"""

from datetime import date, datetime
from database import run_query, run_insert