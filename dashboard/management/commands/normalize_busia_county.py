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

Usage:
    python manage.py normalize_busia_county
"""
from django.core.management.base import BaseCommand

from dashboard.models import (
    CHWRecord, SupervisionRecord, CHPSyncRecord,
    KPIDataPoint, DashUtilDataPoint,
)

BUSIA_ALIASES = ['Busia IS', 'Busia LS', 'busia is', 'busia ls', 'BUSIA IS', 'BUSIA LS']
MODELS = [CHWRecord, SupervisionRecord, CHPSyncRecord, KPIDataPoint, DashUtilDataPoint]


class Command(BaseCommand):
    help = "Merge historical 'Busia IS'/'Busia LS' county values into a single 'Busia'."

    def handle(self, *args, **options):
        total = 0
        for model in MODELS:
            updated = model.objects.filter(county__in=BUSIA_ALIASES).update(county='Busia')
            total += updated
            if updated:
                self.stdout.write(f"{model.__name__}: merged {updated} row(s) into 'Busia'")
        if total:
            self.stdout.write(self.style.SUCCESS(f"Done — {total} row(s) updated in total."))
        else:
            self.stdout.write("Nothing to merge — no 'Busia IS'/'Busia LS' rows found.")
