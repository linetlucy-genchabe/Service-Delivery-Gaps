# Seeds starter target values from the April 2026 Kenya Monthly Program KPIs
# report (Busia uses the Busia IS column, Kisumu uses the Kisumu/IS column —
# not Kisumu 2.0 — per the agreed simplification). These are a starting
# point only: review/adjust them on the Manage Targets page before relying
# on the rankings. Non-FP HIHTs/CHW has no target here since the April
# report didn't restate one separately from the combined HIHTs/CHW figure.

from django.db import migrations

TARGETS = {
    'Busia':   {'preg_per_chp': 1, 'u5_pd_per_chw': 14, 'pnc_blend_pct': 85, 'u1_pd_per_chw': 3.5,
                'anc_4plus_pct': 85, 'total_hihts_per_chw': 25, 'supervision_pct': 65,
                'iccm_referral_pct': 90, 'fp_cyp_per_chw': 8},
    'Kisumu':  {'preg_per_chp': 1, 'u5_pd_per_chw': 10, 'pnc_blend_pct': 85, 'u1_pd_per_chw': 2.5,
                'anc_4plus_pct': 85, 'total_hihts_per_chw': 25, 'supervision_pct': 65,
                'iccm_referral_pct': 90, 'fp_cyp_per_chw': 7},
    'Vihiga':  {'preg_per_chp': 1, 'u5_pd_per_chw': 11, 'pnc_blend_pct': 85, 'u1_pd_per_chw': 2.5,
                'anc_4plus_pct': 85, 'total_hihts_per_chw': 25, 'supervision_pct': 65,
                'iccm_referral_pct': 90, 'fp_cyp_per_chw': 6},
    'Bungoma': {'preg_per_chp': 1, 'u5_pd_per_chw': 5.5, 'pnc_blend_pct': 43, 'u1_pd_per_chw': 1.8,
                'anc_4plus_pct': 85, 'total_hihts_per_chw': 12.5, 'supervision_pct': 33,
                'iccm_referral_pct': 45, 'fp_cyp_per_chw': 3},
}


def seed_targets(apps, schema_editor):
    IndicatorTarget = apps.get_model('dashboard', 'IndicatorTarget')
    for county, metrics in TARGETS.items():
        for key, value in metrics.items():
            IndicatorTarget.objects.update_or_create(
                county=county, metric_key=key, defaults={'target': value}
            )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0012_indicatortarget"),
    ]

    operations = [
        migrations.RunPython(seed_targets, noop_reverse),
    ]
