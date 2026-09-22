"""
management/commands/normalize_busia_county.py

One-time (but safe to run repeatedly) data fix: merges the historical
"Busia IS" / "Busia LS" county values into a single "Busia".

Background: some source files split Busia into two County values ("Busia
IS" and "Busia LS") instead of one. The parsers were fixed to merge these
automatically for anything uploaded from here on (see
dashboard/parsers.py's _normalize_county), but that fix only applies going
forward — rows that were already parsed and saved to the database before
that fix keep whatever county string they were given at the time. This
command backfills those existing rows.

It's idempotent: after the first run, there's nothing left to update, so
running it again (e.g. on every deploy) is a harmless no-op. That's also
why it's wired into railway.toml's startCommand — so this never needs to
be run by hand, and any future re-introduction of the split (e.g. from an
old file being re-uploaded) gets cleaned up automatically on the next
deploy too.

KPIDataPoint and DashUtilDataPoint both carry a unique constraint on
(report, county, sub_county, ...). A plain bulk `.update(county='Busia')`
blows up with an IntegrityError whenever a "Busia" row already exists for
the same report/sub_county/metric/period as a "Busia IS"/"Busia LS" row
(i.e. that data point already exists under the merged name) — which is
exactly what happened on the first deploy of this command and crashed the
app on every startup. So for those two models we work out, in Python,
which aliased rows are free to rename and which collide with an existing
'Busia' row (or with each other), then apply each group with one bulk
query instead of one query per row — the first version did a per-row
save()/IntegrityError round trip, which took ~90 seconds over ~10,000
rows and pushed gunicorn's startup past the healthcheck timeout.

Usage:
    python manage.py normalize_busia_county
"""
from django.core.management.base import BaseCommand

from dashboard.models import (
    CHWRecord, SupervisionRecord, CHPSyncRecord,
    KPIDataPoint, DashUtilDataPoint,
)

BUSIA_ALIASES = ['Busia IS', 'Busia LS', 'busia is', 'busia ls', 'BUSIA IS', 'BUSIA LS']

# Models with no unique constraint on county — a plain bulk update is safe.
SIMPLE_MODELS = [CHWRecord, SupervisionRecord, CHPSyncRecord]

# Models with a unique constraint that includes county, and the other
# fields (besides `report`) that make up that constraint. Two aliased rows
# can collide with an existing 'Busia' row, or with each other.
CONSTRAINED_MODELS = [
    (KPIDataPoint, ['sub_county', 'metric_key', 'year', 'month']),
    (DashUtilDataPoint, ['sub_county']),
]


class Command(BaseCommand):
    help = "Merge historical 'Busia IS'/'Busia LS' county values into a single 'Busia'."

    def handle(self, *args, **options):
        total = 0

        for model in SIMPLE_MODELS:
            updated = model.objects.filter(county__in=BUSIA_ALIASES).update(county='Busia')
            total += updated
            if updated:
                self.stdout.write(f"{model.__name__}: merged {updated} row(s) into 'Busia'")

        for model, key_fields in CONSTRAINED_MODELS:
            aliased = list(model.objects.filter(county__in=BUSIA_ALIASES))
            if not aliased:
                continue

            def key_of(row):
                return (row.report_id,) + tuple(getattr(row, f) for f in key_fields)

            existing_busia_keys = set(
                key_of(row) for row in model.objects.filter(county='Busia').only(
                    'report_id', *key_fields
                )
            )

            to_rename = []
            to_delete_ids = []
            claimed_keys = set()
            for row in aliased:
                key = key_of(row)
                if key in existing_busia_keys or key in claimed_keys:
                    # Either a 'Busia' row already occupies this slot, or
                    # another aliased row (e.g. both 'Busia LS' and 'Busia
                    # IS') got there first in this same pass — either way
                    # the data is already represented, so this row is a
                    # redundant duplicate.
                    to_delete_ids.append(row.pk)
                else:
                    claimed_keys.add(key)
                    row.county = 'Busia'
                    to_rename.append(row)

            if to_delete_ids:
                model.objects.filter(pk__in=to_delete_ids).delete()
            if to_rename:
                model.objects.bulk_update(to_rename, ['county'], batch_size=500)

            total += len(to_rename) + len(to_delete_ids)
            if to_rename or to_delete_ids:
                self.stdout.write(
                    f"{model.__name__}: merged {len(to_rename)} row(s) into 'Busia', "
                    f"removed {len(to_delete_ids)} redundant duplicate(s)"
                )

        if total:
            self.stdout.write(self.style.SUCCESS(f"Done — {total} row(s) updated in total."))
        else:
            self.stdout.write("Nothing to merge — no 'Busia IS'/'Busia LS' rows found.")
