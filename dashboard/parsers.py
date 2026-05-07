"""
parsers.py
----------
Reads the two Excel files and populates CHWRecord / SupervisionRecord rows
for a given UploadBatch. All indicator definitions live here.
"""
import pandas as pd
import numpy as np
from datetime import datetime

from django.db.models import F
from .models import CHWRecord, SupervisionRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _int(val):
    try:
        if isinstance(val, float) and np.isnan(val):
            return 0
        return int(val)
    except (TypeError, ValueError):
        return 0


def _bool_yn(val):
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    if isinstance(val, str):
        return val.strip().lower() in ('yes', 'true', '1')
    return False


def _bool_nullable(val):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    return _bool_yn(val)


def _str(val):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return ''
    return str(val).strip()


# ---------------------------------------------------------------------------
# CHW Detail parser
# ---------------------------------------------------------------------------

def parse_chw_file(batch, file_obj):
    try:
        df = pd.read_excel(file_obj, engine='openpyxl')
    except Exception as e:
        return 0, [f"Could not read CHW file: {e}"]

    required = ['County', 'Sub-County', 'Community Health Unit', 'CHW Name']
    missing = [c for c in required if c not in df.columns]
    if missing:
        return 0, [f"CHW file missing columns: {missing}"]

    records = []
    errors = []

    for i, row in df.iterrows():
        try:
            record = CHWRecord(
                batch=batch,
                county=_str(row.get('County')),
                sub_county=_str(row.get('Sub-County')),
                community_health_unit=_str(row.get('Community Health Unit')),
                chp_area=_str(row.get('CHP Area')),
                chw_name=_str(row.get('CHW Name')),
                chw_id=_str(row.get('CHW ID')),
                username=_str(row.get('Username')),
                is_active=_bool_yn(row.get('Active', 'No')),
                registered_hhs=_int(row.get('Registered HHs', 0)),
                hh_visits=_int(row.get('HH Visits', 0)),
                new_hhs_registered=_int(row.get('New HHs Registered', 0)),
                pregnancies_registered=_int(row.get('Pregnancies Registered', 0)),
                active_pregnancies=_int(row.get('Active Pregnancies', 0)),
                pregnancies_visited=_int(row.get('Pregnancies Visited', 0)),
                pregnancy_visits=_int(row.get('Pregnancy Visits', 0)),
                anc_total_deliveries=_int(row.get('ANC Total Deliveries', 0)),
                deliveries_4plus_anc=_int(row.get('Deliveries 4+ ANC', 0)),
                deliveries_with_anc_data=_int(row.get('Deliveries with ANC Data', 0)),
                first_trimester_registrations=_int(row.get('1st Trimester Registrations', 0)),
                iron_folate_count=_int(row.get('Iron Folate Count', 0)),
                total_deliveries=_int(row.get('Total Deliveries', 0)),
                facility_deliveries=_int(row.get('Facility Deliveries', 0)),
                pnc_48hr_ontime=_int(row.get('PNC 48hr On-time', 0)),
                pnc_3_7d_ontime=_int(row.get('PNC 3-7d On-time', 0)),
                iccm_assessments=_int(row.get('iCCM Assessments', 0)),
                positive_diagnoses_u5=_int(row.get('Positive Diagnoses (U5)', 0)),
                treated_visits_u5=_int(row.get('Treated Visits (U5)', 0)),
                malaria_diagnosed=_int(row.get('Malaria Diagnosed', 0)),
                pneumonia_diagnosed=_int(row.get('Pneumonia Diagnosed', 0)),
                diarrhea_diagnosed=_int(row.get('Diarrhea Diagnosed', 0)),
                malaria_managed=_int(row.get('Malaria Managed', 0)),
                pneumonia_managed=_int(row.get('Pneumonia Managed', 0)),
                diarrhea_managed=_int(row.get('Diarrhea Managed', 0)),
                danger_sign_referred=_int(row.get('Danger Sign Referred', 0)),
                fever_cases=_int(row.get('Fever Cases', 0)),
                fever_tested_rdt=_int(row.get('Fever Tested (RDT)', 0)),
                iccm_referrals_total=_int(row.get('iCCM Referrals Total', 0)),
                iccm_referral_followup=_int(row.get('iCCM Referral Follow-up Completed', 0)),
                iccm_referrals_u2mo=_int(row.get('iCCM Referrals U2mo', 0)),
                iccm_completed_referrals_u2mo=_int(row.get('iCCM Completed Referrals U2mo', 0)),
                u1_positive_diagnoses=_int(row.get('U1 Positive Diagnoses', 0)),
                u1_treated_visits=_int(row.get('U1 Treated Visits', 0)),
                u1_sick_assessments=_int(row.get('U1 Sick Assessments', 0)),
                iz_assessments=_int(row.get('IZ Assessments', 0)),
                iz_fully_immunized=_int(row.get('IZ Fully Immunized 9-23mo', 0)),
                iz_children_9_23mo=_int(row.get('IZ Children 9-23mo', 0)),
                iz_defaulters=_int(row.get('IZ Defaulters', 0)),
                iz_defaulters_followed=_int(row.get('IZ Defaulters Followed Up', 0)),
                iz_defaulters_completed=_int(row.get('IZ Defaulters Completed', 0)),
                fp_assessments=_int(row.get('FP Assessments', 0)),
                fp_new_users=_int(row.get('FP New Users', 0)),
                fp_unique_new_users=_int(row.get('FP Unique New Users', 0)),
                fp_current_users=_int(row.get('FP Current Users', 0)),
                fp_wra_assessed=_int(row.get('FP WRA Assessed', 0)),
                fp_cyp=_int(row.get('FP CYP', 0)),
                fp_non_users_assessed=_int(row.get('FP Non-users Assessed', 0)),
                fp_needing_refill=_int(row.get('FP Needing Refill', 0)),
                fp_refilled=_int(row.get('FP Refilled', 0)),
                fp_referred=_int(row.get('FP Referred', 0)),
                fp_referral_followup=_int(row.get('FP Referral Follow-up', 0)),
                fp_current_users_18_49=_int(row.get('FP Current Users 18-49', 0)),
                fp_wra_assessed_18_49=_int(row.get('FP WRA Assessed 18-49', 0)),
                nutrition_assessments=_int(row.get('Nutrition Assessments', 0)),
                muac_screened=_int(row.get('MUAC Screened', 0)),
                mam_sam_total=_int(row.get('MAM/SAM Total', 0)),
                mam_sam_referred=_int(row.get('MAM/SAM Referred', 0)),
                mam_sam_referral_completed=_int(row.get('MAM/SAM Referral Completed', 0)),
                exclusive_bf=_int(row.get('Exclusive BF', 0)),
                u6mo_bf_assessed=_int(row.get('U6mo BF Assessed', 0)),
                complementary_feeding=_int(row.get('Complementary Feeding', 0)),
                assessed_6_9mo=_int(row.get('Assessed 6-9mo', 0)),
                vitamin_a_covered=_int(row.get('Vitamin A Covered', 0)),
                assessed_6_59mo_vita=_int(row.get('Assessed 6-59mo Vit A', 0)),
                days_synced=_int(row.get('Days Synced', 0)),
                supervised=_bool_yn(row.get('Supervised', 0)),
                supervision_visits=_int(row.get('Supervision Visits', 0)),
            )
            records.append(record)
        except Exception as e:
            errors.append(f"Row {i+2}: {e}")

    CHWRecord.objects.bulk_create(records, batch_size=500)
    return len(records), errors


# ---------------------------------------------------------------------------
# Supervision parser
# ---------------------------------------------------------------------------

def parse_supervision_file(batch, file_obj):
    try:
        df = pd.read_excel(file_obj, engine='openpyxl')
    except Exception as e:
        return 0, [f"Could not read Supervision file: {e}"]

    required = ['County', 'Sub-County', 'Community Health Unit', 'Date', 'CHV Name']
    missing = [c for c in required if c not in df.columns]
    if missing:
        return 0, [f"Supervision file missing columns: {missing}"]

    records = []
    errors = []

    for i, row in df.iterrows():
        try:
            raw_date = row.get('Date')
            if isinstance(raw_date, str):
                visit_date = datetime.strptime(raw_date.strip(), '%Y-%m-%d').date()
            elif hasattr(raw_date, 'date'):
                visit_date = raw_date.date()
            else:
                visit_date = datetime.strptime(str(raw_date)[:10], '%Y-%m-%d').date()

            def _safe_float(val):
                try:
                    if isinstance(val, float) and np.isnan(val):
                        return None
                    return float(val)
                except (TypeError, ValueError):
                    return None

            record = SupervisionRecord(
                batch=batch,
                county=_str(row.get('County')),
                sub_county=_str(row.get('Sub-County')),
                community_health_unit=_str(row.get('Community Health Unit')),
                visit_date=visit_date,
                chv_name=_str(row.get('CHV Name')),
                chv_uuid=_str(row.get('CHV UUID')),
                is_available=_bool_yn(row.get('Is Available', 'yes')),
                visit_sections=_str(row.get('Visit Sections')),
                has_essential_medicines=_bool_nullable(row.get('Has Essential Medicines')),
                medicines_lacking=_str(row.get('Medicines Lacking')),
                assessment_score=_safe_float(row.get('Assessment Score')),
                assessment_denominator=_int(row.get('Assessment Denominator', 0)),
                has_all_tools=_bool_nullable(row.get('Has All Tools')),
                has_ppe=_bool_nullable(row.get('Has PPE')),
                supervisor_area=_str(row.get('Supervisor Area')),
                supervisor_phone=_str(row.get('Supervisor Phone')),
                next_steps=_str(row.get('Next Steps')),
                overall_observations=_str(row.get('Overall Observations')),
            )
            records.append(record)
        except Exception as e:
            errors.append(f"Row {i+2}: {e}")

    SupervisionRecord.objects.bulk_create(records, batch_size=500)
    return len(records), errors


# ---------------------------------------------------------------------------
# Indicator computation
# ---------------------------------------------------------------------------

def compute_indicators(chw_qs, sup_qs, period_type='monthly'):
    from django.db.models import Sum, Count, Q

    LOW_HH_THRESHOLD = 50 if period_type == 'monthly' else 12

    active_qs = chw_qs.filter(is_active=True)

    total_active   = active_qs.count()
    total_inactive = chw_qs.filter(is_active=False).count()

    # Supervision
    supervised_count   = active_qs.filter(supervised=True).count()
    unsupervised_count = active_qs.filter(supervised=False).count()
    supervision_rate   = round(supervised_count / total_active * 100, 1) if total_active else 0

    # Low performers — split into two groups
    low_performers_unsupervised = active_qs.filter(
        hh_visits__lt=LOW_HH_THRESHOLD, supervised=False
    ).count()
    low_performers_supervised = active_qs.filter(
        hh_visits__lt=LOW_HH_THRESHOLD, supervised=True
    ).count()
    low_performer_count = low_performers_unsupervised + low_performers_supervised

    # ANC gap — CHPs with active pregnancies who didn't visit all of them
    # A CHP has a gap if active_pregnancies > pregnancies_visited
    anc_gap_chps = active_qs.filter(
        active_pregnancies__gt=F('pregnancies_visited')
    ).exclude(active_pregnancies=0).count()

    agg = active_qs.aggregate(
        preg_reg=Sum('pregnancies_registered'),
        active_preg=Sum('active_pregnancies'),
        preg_vis=Sum('pregnancies_visited'),
        anc_4plus=Sum('deliveries_4plus_anc'),
        anc_with_data=Sum('deliveries_with_anc_data'),
        first_trim=Sum('first_trimester_registrations'),
        iron_folate=Sum('iron_folate_count'),
        total_del=Sum('total_deliveries'),
        facility_del=Sum('facility_deliveries'),
        pnc_48=Sum('pnc_48hr_ontime'),
        iccm=Sum('iccm_assessments'),
        iz_assessed=Sum('iz_assessments'),
        iz_immunized=Sum('iz_fully_immunized'),
        iz_defaulters=Sum('iz_defaulters'),
        iz_def_followup=Sum('iz_defaulters_followed'),
        fp_needing=Sum('fp_needing_refill'),
        fp_refilled=Sum('fp_refilled'),
        muac=Sum('muac_screened'),
        mam_sam=Sum('mam_sam_total'),
        mam_referred=Sum('mam_sam_referred'),
        hh_visits_total=Sum('hh_visits'),
        days_synced_total=Sum('days_synced'),
    )

    active_preg  = agg['active_preg'] or 0
    preg_vis     = agg['preg_vis'] or 0
    # Total unvisited pregnancies across all CHPs
    total_anc_gap = max(active_preg - preg_vis, 0)
    anc_gap_pct   = round(total_anc_gap / active_preg * 100, 1) if active_preg else 0

    anc_4plus      = agg['anc_4plus'] or 0
    anc_with_data  = agg['anc_with_data'] or 0
    anc_4plus_rate = round(anc_4plus / anc_with_data * 100, 1) if anc_with_data else 0

    iz_assessed  = agg['iz_assessed'] or 0
    iz_immunized = agg['iz_immunized'] or 0
    iz_rate      = round(iz_immunized / iz_assessed * 100, 1) if iz_assessed else 0

    iz_def       = agg['iz_defaulters'] or 0
    iz_def_fu    = agg['iz_def_followup'] or 0
    iz_def_rate  = round(iz_def_fu / iz_def * 100, 1) if iz_def else 0

    fp_need    = agg['fp_needing'] or 0
    fp_ref     = agg['fp_refilled'] or 0
    fp_gap     = max(fp_need - fp_ref, 0)
    fp_gap_pct = round(fp_gap / fp_need * 100, 1) if fp_need else 0

    muac     = agg['muac'] or 0
    mam_sam  = agg['mam_sam'] or 0
    mam_ref  = agg['mam_referred'] or 0
    mam_rate = round(mam_ref / mam_sam * 100, 1) if mam_sam else 0

    # Same-day 5+ supervision flag
    same_day_flags = (
        sup_qs
        .values('community_health_unit', 'visit_date')
        .annotate(count=Count('id'))
        .filter(count__gte=5)
        .order_by('-count')
    )

    return {
        'total_active': total_active,
        'total_inactive': total_inactive,
        'total_chps': chw_qs.count(),
        'supervised_count': supervised_count,
        'unsupervised_count': unsupervised_count,
        'supervision_rate': supervision_rate,
        'same_day_flags': list(same_day_flags),
        'same_day_flags_count': same_day_flags.count(),
        'low_performer_count': low_performer_count,
        'low_performers_unsupervised': low_performers_unsupervised,
        'low_performers_supervised': low_performers_supervised,
        'low_hh_threshold': LOW_HH_THRESHOLD,
        # ANC
        'anc_gap_chps': anc_gap_chps,
        'active_pregnancies': active_preg,
        'pregnancies_visited': preg_vis,
        'total_anc_gap': total_anc_gap,
        'anc_gap_pct': anc_gap_pct,
        'anc_4plus_rate': anc_4plus_rate,
        'first_trimester': agg['first_trim'] or 0,
        'iron_folate': agg['iron_folate'] or 0,
        'total_deliveries': agg['total_del'] or 0,
        'facility_deliveries': agg['facility_del'] or 0,
        'facility_delivery_rate': round((agg['facility_del'] or 0) / (agg['total_del'] or 1) * 100, 1),
        'pnc_48hr': agg['pnc_48'] or 0,
        'iccm_assessments': agg['iccm'] or 0,
        'iz_assessed': iz_assessed,
        'iz_immunized': iz_immunized,
        'iz_rate': iz_rate,
        'iz_defaulters': iz_def,
        'iz_def_followup_rate': iz_def_rate,
        'fp_needing_refill': fp_need,
        'fp_refilled': fp_ref,
        'fp_gap': fp_gap,
        'fp_gap_pct': fp_gap_pct,
        'muac_screened': muac,
        'mam_sam_total': mam_sam,
        'mam_referral_rate': mam_rate,
        'hh_visits_total': agg['hh_visits_total'] or 0,
        'days_synced_total': agg['days_synced_total'] or 0,
    }
