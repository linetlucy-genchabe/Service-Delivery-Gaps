"""
Parser for Dashboard Utilization Report Excel files.
Reads county-level from CHA Utilisation sheet and
sub-county level from Executive Summary sheet.
"""
import re
import math
import pandas as pd
from .models import DashUtilReport, DashUtilDataPoint


def _safe_pct(val):
    """Convert '96.4%' or 0.964 or 96.4 to float percentage."""
    if val is None:
        return None
    try:
        s = str(val).strip().replace('%', '')
        f = float(s)
        if math.isnan(f):
            return None
        # If value is between 0 and 1, it's a decimal fraction
        return round(f * 100, 1) if f <= 1.0 else round(f, 1)
    except (ValueError, TypeError):
        return None


def parse_dash_util_report(report: DashUtilReport):
    """
    Parse county and sub-county utilization from the report file.
    Returns (rows_created, errors).
    """
    DashUtilDataPoint.objects.filter(report=report).delete()

    try:
        xl = pd.ExcelFile(report.file, engine='openpyxl')
    except Exception as e:
        return 0, [f"Could not open file: {e}"]

    errors = []
    to_create = []

    # -----------------------------------------------------------------------
    # 1. COUNTY level — from 'CHA Utilisation' sheet
    # -----------------------------------------------------------------------
    try:
        df = pd.read_excel(xl, sheet_name='CHA Utilisation', header=2)
        # Rename columns
        df.columns = [str(c).strip() for c in df.columns]

        # Find the active % column — monthly uses 'month %', weekly uses '7-day %'
        pct_col = None
        for candidate in ['month %', '7-day %', 'month%', '7-day%']:
            if candidate in df.columns:
                pct_col = candidate
                break

        active_col = 'Active (month)' if report.period_type == 'monthly' else 'Active (7-day)'
        total_col  = 'Verified CHAs'
        county_col = df.columns[0]  # first column is county

        if pct_col:
            for _, row in df.iterrows():
                county = str(row.get(county_col, '')).strip()
                if not county or county.upper() in ('COUNTY', 'TOTAL', 'NAN', ''):
                    continue
                pct   = _safe_pct(row.get(pct_col))
                active = int(row[active_col]) if active_col in df.columns and not pd.isna(row.get(active_col, None)) else None
                total  = int(row[total_col])  if total_col  in df.columns and not pd.isna(row.get(total_col, None))  else None
                to_create.append(DashUtilDataPoint(
                    report=report, county=county, sub_county='',
                    active_users=active, total_users=total, utilization_pct=pct
                ))
    except Exception as e:
        errors.append(f"CHA Utilisation sheet error: {e}")

    # -----------------------------------------------------------------------
    # 2. SUB-COUNTY level — from 'Executive Summary' sheet rows 30+
    # -----------------------------------------------------------------------
    try:
        df_ex = pd.read_excel(xl, sheet_name='Executive Summary', header=None)

        # Find the sub-county section header row
        sc_start = None
        for i, row in df_ex.iterrows():
            if str(row.iloc[0]).strip().lower() in ('engagement by sub county', 'sub county'):
                sc_start = i
                break

        if sc_start is not None:
            # Next row after header is column names
            col_row = df_ex.iloc[sc_start + 1]
            cols    = [str(c).strip() for c in col_row.values]

            # Find relevant column indices
            sc_idx     = 0  # Sub County
            county_idx = 1  # County
            try:
                pct_idx = cols.index('% CU Active')
            except ValueError:
                pct_idx = None

            try:
                active_idx = cols.index('Active CU Users')
            except ValueError:
                active_idx = None

            try:
                total_idx = cols.index('Total CU Users')
            except ValueError:
                total_idx = None

            # Read data rows
            for i in range(sc_start + 2, len(df_ex)):
                row = df_ex.iloc[i]
                sc = str(row.iloc[sc_idx]).strip()
                if not sc or sc.lower() in ('nan', 'sub county', ''):
                    continue
                county = str(row.iloc[county_idx]).strip() if len(row) > county_idx else ''
                if county.lower() in ('nan', ''):
                    continue

                pct    = _safe_pct(row.iloc[pct_idx])   if pct_idx    is not None else None
                active = int(row.iloc[active_idx]) if active_idx is not None and not pd.isna(row.iloc[active_idx]) else None
                total  = int(row.iloc[total_idx])  if total_idx  is not None and not pd.isna(row.iloc[total_idx])  else None

                to_create.append(DashUtilDataPoint(
                    report=report, county=county, sub_county=sc,
                    active_users=active, total_users=total, utilization_pct=pct
                ))
    except Exception as e:
        errors.append(f"Executive Summary sheet error: {e}")

    try:
        created = DashUtilDataPoint.objects.bulk_create(
            to_create, ignore_conflicts=True, batch_size=200)
        rows_created = len(created)
    except Exception as e:
        errors.append(f"Database error: {e}")
        rows_created = 0

    return rows_created, errors