"""
management/commands/reprocess_batches.py

Re-parses all uploaded Excel files already on disk and repopulates
CHWRecord and SupervisionRecord rows from scratch.

Usage:
    python manage.py reprocess_batches               # reprocess all batches
    python manage.py reprocess_batches --batch 3     # reprocess one batch by ID
    python manage.py reprocess_batches --chw-only    # only reprocess CHW records
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from dashboard.models import UploadBatch, CHWRecord, SupervisionRecord
from dashboard.parsers import parse_chw_file, parse_supervision_file
import os


class Command(BaseCommand):
    help = 'Reprocess uploaded Excel files to repopulate database records'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch', type=int, default=None,
            help='ID of a specific batch to reprocess (default: all batches)'
        )
        parser.add_argument(
            '--chw-only', action='store_true',
            help='Only reprocess CHW Detail records (skip supervision)'
        )
        parser.add_argument(
            '--supervision-only', action='store_true',
            help='Only reprocess Supervision records (skip CHW)'
        )

    def handle(self, *args, **options):
        batch_id   = options.get('batch')
        chw_only   = options.get('chw_only')
        sup_only   = options.get('supervision_only')

        if batch_id:
            batches = UploadBatch.objects.filter(pk=batch_id)
            if not batches.exists():
                self.stderr.write(f'Batch ID {batch_id} not found.')
                return
        else:
            batches = UploadBatch.objects.all().order_by('id')

        self.stdout.write(f'Found {batches.count()} batch(es) to reprocess.\n')

        for batch in batches:
            self.stdout.write(f'\n--- Batch {batch.pk}: {batch.label} ---')

            # CHW records
            if not sup_only:
                chw_path = os.path.join(settings.MEDIA_ROOT, str(batch.chw_file))
                if not os.path.exists(chw_path):
                    self.stderr.write(f'  CHW file not found on disk: {chw_path}')
                else:
                    self.stdout.write(f'  Deleting existing CHW records...')
                    deleted = CHWRecord.objects.filter(batch=batch).delete()
                    self.stdout.write(f'  Deleted {deleted[0]} CHW records.')

                    self.stdout.write(f'  Reparsing CHW file: {chw_path}')
                    with open(chw_path, 'rb') as f:
                        rows, errors = parse_chw_file(batch, f)

                    self.stdout.write(
                        self.style.SUCCESS(f'  ✓ CHW: {rows} records saved.')
                    )
                    if errors:
                        self.stderr.write(f'  Warnings ({len(errors)}):')
                        for e in errors[:5]:
                            self.stderr.write(f'    {e}')

            # Supervision records
            if not chw_only:
                sup_path = os.path.join(settings.MEDIA_ROOT, str(batch.supervision_file))
                if not os.path.exists(sup_path):
                    self.stderr.write(f'  Supervision file not found on disk: {sup_path}')
                else:
                    self.stdout.write(f'  Deleting existing Supervision records...')
                    deleted = SupervisionRecord.objects.filter(batch=batch).delete()
                    self.stdout.write(f'  Deleted {deleted[0]} Supervision records.')

                    self.stdout.write(f'  Reparsing Supervision file: {sup_path}')
                    with open(sup_path, 'rb') as f:
                        rows, errors = parse_supervision_file(batch, f)

                    self.stdout.write(
                        self.style.SUCCESS(f'  ✓ Supervision: {rows} records saved.')
                    )
                    if errors:
                        self.stderr.write(f'  Warnings ({len(errors)}):')
                        for e in errors[:5]:
                            self.stderr.write(f'    {e}')

        self.stdout.write(self.style.SUCCESS('\nAll batches reprocessed successfully.'))