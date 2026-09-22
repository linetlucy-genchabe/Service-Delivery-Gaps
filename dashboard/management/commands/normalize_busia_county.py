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
app on every startup. So for those two models we go row by row: rename a
row to 'Busia' when that's free, or just delete it as a redundant
duplicate when a 'Busia' row already occupies that slot.

Usage:
    python manage.py normalize_busia_county
"""
from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction

from dashboard.models import (
    CHWRecord, SupervisionRecord, CHPSyncRecord,
    KPIDataPoint, DashUtilDataPoint,
)

BUSIA_ALIASES = ['Busia IS', 'Busia LS', 'busia is', 'busia ls', 'BUSIA IS', 'BUSIA LS']

# Models with no unique constraint on county — a plain bulk update is safe.
SIMPLE_MODELS = [CHWRecord, SupervisionRecord, CHPSyncRecord]

# Models with a unique constraint that includes county — must merge row by
# row, since two aliased rows can collide with an existing 'Busia' row.
CONSTRAINED_MODELS = [KPIDataPoint, DashUtilDataPoint]


class Command(BaseCommand):
    help = "Merge historical 'Busia IS'/'Busia LS' county values into a single 'Busia'."

    def handle(self, *args, **options):
        total = 0

        for model in SIMPLE_MODELS:
            updated = model.objects.filter(county__in=BUSIA_ALIASES).update(county='Busia')
            total += updated
            if updated:
                self.stdout.write(f"{model.__name__}: merged {updated} row(s) into 'Busia'")

        for model in CONSTRAINED_MODELS:
            renamed = 0
            deleted_dupes = 0
            rows = list(model.objects.filter(county__in=BUSIA_ALIASES))
            for row in rows:
                try:
                    with transaction.atomic():
                        row.county = 'Busia'
                        row.save(update_fields=['county'])
                    renamed += 1
                except IntegrityError:
                    # A 'Busia' row already exists for this exact
                    # report/sub_county/metric/period — the data is
                    # already represented, so this aliased row is a
                    # redundant duplicate and can be dropped.
                    model.objects.filter(pk=row.pk).delete()
                    deleted_dupes += 1
            total += renamed + deleted_dupes
            if renamed or deleted_dupes:
                self.stdout.write(
                    f"{model.__name__}: merged {renamed} row(s) into 'Busia', "
                    f"removed {deleted_dupes} redundant duplicate(s)"
                )

        if total:
            self.stdout.write(self.style.SUCCESS(f"Done — {total} row(s) updated in total."))
        else:
            self.stdout.write("Nothing to merge — no 'Busia IS'/'Busia LS' rows found.")
