"""
Parser for KE Monthly Report Excel files.
Reads KPIs, PIs and HIHTs sheets for each county + Kenya level.
Stores data as KPIDataPoint records.
"""
import re
import math
import pandas as pd
from .models import KPIReport, KPIDataPoint

# ---------------------------------------------------------------------------
# Metric key mapping — maps our internal key to (sheet_suffix, metric_name)
# ---------------------------------------------------------------------------
METRIC_MAP = {
    'active_chps':          ('KPIs', 'Total Active CHWs (1-month)'),
    'hh_coverage_pct':      ('PIs',  '1-month Coverage: % unique HH visits per month per CHW'),
    'u5_assessments':       ('PIs',  'Total Under-5 Assessments'),
    'u5_children':          ('PIs',  'Total U5 Children'),
    'sick_children_avg':    ('PIs',  '# of U5 children with positive diagnoses/CHW'),
    'iccm_assessments_per': ('PIs',  '<5 Assessments per CHW'),
    'iccm_ref_completed':   ('KPIs', '% sick child facility referrals completed as confirmed by client'),
    'pnc_48hr':             ('HIHTs','PNC 48 hours'),
    'pnc_3_7d':             ('HIHTs','PNC visits 3 days to 1 week'),
    'facility_deliveries':  ('HIHTs','Facility Deliveries'),
    'preg_per_chp':         ('KPIs', 'Pregnancies registered per CHW'),
    'sync_pct':             ('KPIs', '% of CHWs who have synced their data per week'),
    'supervision_pct':      ('KPIs', '% of CHWs w/ supportive supervision in the last 1 month'),
}

# Map month abbreviation in column names to month number
MONTH_ABBR = {
    'Jan':1,'Feb':2,'Mar':3,'Apr':4,'May':5,'Jun':6,
    'Jul':7,'Aug':8,'Sep':9,'Oct':10,'Nov':11,'Dec':12
}

COUNTIES = ['Kenya', 'Kisumu', 'Bungoma', 'Vihiga', 'Busia IS', 'Busia LS', 'KisumuIS2.0']

COUNTY_SHEET_MAP = {
    'Kenya':      'Kenya',
    'Kisumu':     'Kisumu',
    'Bungoma':    'Bungoma',
    'Vihiga':     'Vihiga',
    'Busia IS':   'Busia IS',
    'Busia LS':   'Busia LS',
    'KisumuIS2.0':'KisumuIS2.0',
}

def _parse_col(col):
    """Parse column name like 'Jan26' -> (month_int, year_int) or None."""
    m = re.match(r'^([A-Za-z]{3})(\d{2})$', str(col))
    if not m:
        return None
    mon = MONTH_ABBR.get(m.group(1))
    if not mon:
        return None
    year = 2000 + int(m.group(2))
    return (mon, year)

def _safe_float(val):
    try:
        f = float(val)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None

def parse_kpi_report(report: KPIReport):
    """
    Parse all sheets from the uploaded KPI report file.
    Creates KPIDataPoint records.
    Returns (rows_created, errors).
    """
    # Clear existing data for this report
    KPIDataPoint.objects.filter(report=report).delete()

    try:
        xl = pd.ExcelFile(report.file, engine='openpyxl')
    except Exception as e:
        return 0, [f"Could not open file: {e}"]

    rows_created = 0
    errors = []
    to_create = []

    for county, sheet_prefix in COUNTY_SHEET_MAP.items():
        county_name = '' if county == 'Kenya' else county

        for metric_key, (sheet_suffix, metric_name) in METRIC_MAP.items():
            sheet_name = f"{sheet_prefix}_{sheet_suffix}"
            if sheet_name not in xl.sheet_names:
                continue

            try:
                df = pd.read_excel(xl, sheet_name=sheet_name)
            except Exception as e:
                errors.append(f"Could not read sheet {sheet_name}: {e}")
                continue

            # Filter rows for this metric
            metric_rows = df[df['Metric'] == metric_name]
            if metric_rows.empty:
                continue

            # Get month columns
            month_cols = [c for c in df.columns if _parse_col(c)]

            for _, row in metric_rows.iterrows():
                raw_subloc = str(row.get('Sublocation', '')).strip()

                # Determine sub_county
                # County-level rows have county name in caps or match county
                if raw_subloc.upper() == raw_subloc or raw_subloc.upper() == county.upper() or county.upper() in raw_subloc.upper():
                    sub_county = ''
                else:
                    sub_county = raw_subloc

                for col in month_cols:
                    parsed = _parse_col(col)
                    if not parsed:
                        continue
                    month, year = parsed
                    val = _safe_float(row[col])

                    to_create.append(KPIDataPoint(
                        report=report,
                        county=county_name,
                        sub_county=sub_county,
                        metric_key=metric_key,
                        year=year,
                        month=month,
                        value=val,
                    ))

    # Bulk create ignoring duplicates
    try:
        created = KPIDataPoint.objects.bulk_create(
            to_create, ignore_conflicts=True, batch_size=500)
        rows_created = len(created)
    except Exception as e:
        errors.append(f"Database error: {e}")

    return rows_created, errors