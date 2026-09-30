"""
edd_parser.py
-------------
Parses an uploaded EDD (Expected Delivery Date) list into EDDRecord rows.

This is a pregnancy-level export shared separately from the other reports
(CHW Detail, Supervision, Sync, KPI) — one row per pregnancy, carrying the
CHW hierarchy it sits under and its effective EDD, used to visualize
upcoming deliveries.
"""
import pandas as pd

from .models import EDDRecord
from .parsers import _normalize_county, _str

# Source column name -> EDDRecord field name.
COLUMN_MAP = {
    'pregnancy_id':                       'pregnancy_id',
    'county':                             'county',
    'subcounty':                          'sub_county',
    'community_unit':                     'community_unit',
    'chw_name':                           'chw_name',
    'chw_uuid':                           'chw_uuid',
    'member_name':                        'member_name',
    'household_name':                     'household_name',
    'effective_edd_date':                 'effective_edd_date',
    'initial_edd_date':                   'initial_edd_date',
    'latest_edd_date':                    'latest_edd_date',
    'has_edd_shift_flag':                 'has_edd_shift_flag',
    'edd_shift_days':                     'edd_shift_days',
    'has_no_edd_captured':                'has_no_edd_captured',
    'gestational_weeks_at_registration':  'gestational_weeks_at_registration',
    'chp_visit_count':                    'chp_visit_count',
    'last_visit_date':                    'last_visit_date',
    'first_deviation':                    'status',
}

DATE_FIELDS = {'effective_edd_date', 'initial_edd_date', 'latest_edd_date', 'last_visit_date'}
INT_FIELDS  = {'edd_shift_days', 'gestational_weeks_at_registration', 'chp_visit_count'}
BOOL_FIELDS = {'has_edd_shift_flag', 'has_no_edd_captured'}


def _date(val):
    """Parses an EDD-list date cell. Some exports use 1970-01-01 (or blank/
    '[NULL]') as a "not captured" placeholder rather than leaving it empty."""
    if val is None or val == '' or val == '[NULL]':
        return None
    try:
        d = pd.to_datetime(val)
    except (TypeError, ValueError):
        return None
    if pd.isna(d) or d.year <= 1970:
        return None
    return d.date()


def _int(val):
    if val is None or val == '' or val == '[NULL]':
        return None
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return None


def _bool(val):
    return _int(val) == 1


def parse_edd_file(batch, file_obj):
    """Reads the uploaded EDD list and creates one EDDRecord per row.
    Returns the number of records created."""
    df = pd.read_excel(file_obj, engine='openpyxl')
    df.columns = [str(c).strip() for c in df.columns]

    records = []
    for _, row in df.iterrows():
        kwargs = {'batch': batch}
        for src_col, field in COLUMN_MAP.items():
            if src_col not in df.columns:
                continue
            val = row.get(src_col)
            if field in DATE_FIELDS:
                val = _date(val)
            elif field in INT_FIELDS:
                val = _int(val)
            elif field in BOOL_FIELDS:
                val = _bool(val)
            elif field == 'county':
                val = _normalize_county(val)
            else:
                val = _str(val)
            kwargs[field] = val
        records.append(EDDRecord(**kwargs))

    EDDRecord.objects.bulk_create(records, batch_size=500)
    return len(records)
