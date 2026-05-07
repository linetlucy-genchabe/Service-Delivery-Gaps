"""
views.py
--------
All views for the CHA Dashboard.
"""
import json
import csv
import io
from datetime import date

from django import forms as django_forms
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.views.decorators.http import require_GET

from .models import UploadBatch, CHWRecord, SupervisionRecord
from .forms import LoginForm, UploadBatchForm
from .parsers import parse_chw_file, parse_supervision_file, compute_indicators


def healthz(request):
    from django.http import HttpResponse
    return HttpResponse("ok", status=200)


from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Count, Q
from django.views.decorators.http import require_GET

from .models import UploadBatch, CHWRecord, SupervisionRecord
from .forms import LoginForm, UploadBatchForm
from .parsers import parse_chw_file, parse_supervision_file, compute_indicators


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        return redirect(request.GET.get('next', 'dashboard'))
    return render(request, 'dashboard/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('login')


def is_uploader(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

@login_required
@user_passes_test(is_uploader)
def upload_view(request):
    form = UploadBatchForm(request.POST or None, request.FILES or None)
    if request.method == 'POST':
        if form.is_valid():
            batch = form.save(commit=False)
            batch.uploaded_by = request.user
            batch.year  = int(form.cleaned_data['year'])
            batch.month = int(form.cleaned_data['month'])
            batch.save()

            chw_rows, chw_errors = parse_chw_file(batch, request.FILES['chw_file'])
            sup_rows, sup_errors = parse_supervision_file(batch, request.FILES['supervision_file'])

            all_errors = chw_errors + sup_errors
            if all_errors:
                messages.warning(request, f"Upload completed with {len(all_errors)} row-level warnings. "
                                          f"CHW rows: {chw_rows}, Supervision rows: {sup_rows}.")
            else:
                messages.success(request, f"Upload successful! {chw_rows} CHW records and "
                                          f"{sup_rows} supervision records saved for {batch.label}.")
            return redirect('dashboard')
        else:
            messages.error(request, "Please correct the errors below.")

    batches = UploadBatch.objects.all().order_by('-year', '-month', '-week_start_date')
    return render(request, 'dashboard/upload.html', {'form': form, 'batches': batches})


@login_required
@user_passes_test(is_uploader)
def delete_batch_view(request, pk):
    batch = get_object_or_404(UploadBatch, pk=pk)
    if request.method == 'POST':
        label = batch.label
        batch.delete()
        messages.success(request, f"Batch '{label}' deleted successfully.")
    return redirect('upload')


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@login_required
def dashboard_view(request):
    # All available batches for the filter dropdowns
    batches = UploadBatch.objects.all().order_by('-year', '-month', '-week_start_date')

    # Selected filters
    selected_batch_id  = request.GET.get('batch')
    selected_county    = request.GET.get('county', '')
    selected_subcounty = request.GET.get('sub_county', '')
    selected_chu       = request.GET.get('chu', '')

    selected_batch = None
    indicators     = None
    filter_options = {}

    if selected_batch_id:
        selected_batch = get_object_or_404(UploadBatch, pk=selected_batch_id)

        chw_qs = CHWRecord.objects.filter(batch=selected_batch)
        sup_qs = SupervisionRecord.objects.filter(batch=selected_batch)

        # Cascading filter values for dropdowns
        filter_options['counties'] = (
            chw_qs.values_list('county', flat=True).distinct().order_by('county')
        )

        if selected_county:
            chw_qs = chw_qs.filter(county=selected_county)
            sup_qs = sup_qs.filter(county=selected_county)
            filter_options['sub_counties'] = (
                chw_qs.values_list('sub_county', flat=True).distinct().order_by('sub_county')
            )

        if selected_subcounty:
            chw_qs = chw_qs.filter(sub_county=selected_subcounty)
            sup_qs = sup_qs.filter(sub_county=selected_subcounty)
            filter_options['chus'] = (
                chw_qs.values_list('community_health_unit', flat=True).distinct().order_by('community_health_unit')
            )

        if selected_chu:
            chw_qs = chw_qs.filter(community_health_unit=selected_chu)
            sup_qs = sup_qs.filter(community_health_unit=selected_chu)

        indicators = compute_indicators(chw_qs, sup_qs, selected_batch.period_type)

    context = {
        'batches': batches,
        'selected_batch': selected_batch,
        'selected_batch_id': selected_batch_id or '',
        'selected_county': selected_county,
        'selected_subcounty': selected_subcounty,
        'selected_chu': selected_chu,
        'filter_options': filter_options,
        'indicators': indicators,
        'is_uploader': is_uploader(request.user),
    }
    return render(request, 'dashboard/dashboard.html', context)


# ---------------------------------------------------------------------------
# API endpoints (JSON) – called by JS for drill-down tables
# ---------------------------------------------------------------------------

@login_required
@require_GET
def api_unsupervised(request):
    batch_id    = request.GET.get('batch')
    county      = request.GET.get('county', '')
    sub_county  = request.GET.get('sub_county', '')
    chu         = request.GET.get('chu', '')

    if not batch_id:
        return JsonResponse({'error': 'batch required'}, status=400)

    qs = CHWRecord.objects.filter(batch_id=batch_id, is_active=True, supervised=False)
    if county:     qs = qs.filter(county=county)
    if sub_county: qs = qs.filter(sub_county=sub_county)
    if chu:        qs = qs.filter(community_health_unit=chu)

    data = list(qs.values(
        'county', 'sub_county', 'community_health_unit', 'chp_area',
        'chw_name', 'chw_id', 'hh_visits', 'days_synced', 'supervision_visits'
    ).order_by('county', 'sub_county', 'community_health_unit', 'chw_name'))

    return JsonResponse({'results': data, 'count': len(data)})


@login_required
@require_GET
def api_low_performers(request):
    """Low performers split by supervision status."""
    batch_id    = request.GET.get('batch')
    county      = request.GET.get('county', '')
    sub_county  = request.GET.get('sub_county', '')
    chu         = request.GET.get('chu', '')
    group       = request.GET.get('group', 'unsupervised')  # 'unsupervised' or 'supervised'

    if not batch_id:
        return JsonResponse({'error': 'batch required'}, status=400)

    batch = get_object_or_404(UploadBatch, pk=batch_id)
    threshold = 50 if batch.period_type == 'monthly' else 12

    qs = CHWRecord.objects.filter(batch_id=batch_id, is_active=True, hh_visits__lt=threshold)
    if group == 'supervised':
        qs = qs.filter(supervised=True)
    else:
        qs = qs.filter(supervised=False)
    if county:     qs = qs.filter(county=county)
    if sub_county: qs = qs.filter(sub_county=sub_county)
    if chu:        qs = qs.filter(community_health_unit=chu)

    data = list(qs.values(
        'county', 'sub_county', 'community_health_unit', 'chp_area',
        'chw_name', 'chw_id', 'hh_visits', 'days_synced', 'supervision_visits'
    ).order_by('hh_visits', 'community_health_unit'))

    return JsonResponse({'results': data, 'count': len(data), 'threshold': threshold, 'group': group})


@login_required
@require_GET
def api_anc_gap(request):
    """CHPs with active pregnancies they did not fully visit."""
    from django.db.models import F as DjangoF
    batch_id    = request.GET.get('batch')
    county      = request.GET.get('county', '')
    sub_county  = request.GET.get('sub_county', '')
    chu         = request.GET.get('chu', '')

    if not batch_id:
        return JsonResponse({'error': 'batch required'}, status=400)

    qs = CHWRecord.objects.filter(batch_id=batch_id, is_active=True)
    if county:     qs = qs.filter(county=county)
    if sub_county: qs = qs.filter(sub_county=sub_county)
    if chu:        qs = qs.filter(community_health_unit=chu)

    # CHPs where active_pregnancies > pregnancies_visited AND active_pregnancies > 0
    qs = qs.exclude(active_pregnancies=0).filter(
        active_pregnancies__gt=DjangoF('pregnancies_visited')
    )

    data = list(qs.values(
        'county', 'sub_county', 'community_health_unit', 'chp_area',
        'chw_name', 'chw_id', 'active_pregnancies', 'pregnancies_visited'
    ).order_by('community_health_unit', 'chw_name'))

    # Add gap per CHP
    for row in data:
        row['gap'] = row['active_pregnancies'] - row['pregnancies_visited']

    return JsonResponse({'results': data, 'count': len(data)})


@login_required
@require_GET
def api_same_day_flags(request):
    batch_id    = request.GET.get('batch')
    county      = request.GET.get('county', '')
    sub_county  = request.GET.get('sub_county', '')
    chu         = request.GET.get('chu', '')

    if not batch_id:
        return JsonResponse({'error': 'batch required'}, status=400)

    qs = SupervisionRecord.objects.filter(batch_id=batch_id)
    if county:     qs = qs.filter(county=county)
    if sub_county: qs = qs.filter(sub_county=sub_county)
    if chu:        qs = qs.filter(community_health_unit=chu)

    flags = (
        qs.values('county', 'sub_county', 'community_health_unit', 'visit_date')
        .annotate(count=Count('id'))
        .filter(count__gte=5)
        .order_by('-count', 'community_health_unit')
    )

    data = []
    for f in flags:
        data.append({
            'county': f['county'],
            'sub_county': f['sub_county'],
            'community_health_unit': f['community_health_unit'],
            'visit_date': f['visit_date'].strftime('%d %b %Y') if f['visit_date'] else '',
            'count': f['count'],
        })

    return JsonResponse({'results': data, 'count': len(data)})


# ---------------------------------------------------------------------------
# Download endpoints (CSV)
# ---------------------------------------------------------------------------

@login_required
def download_unsupervised(request):
    batch_id    = request.GET.get('batch')
    county      = request.GET.get('county', '')
    sub_county  = request.GET.get('sub_county', '')
    chu         = request.GET.get('chu', '')

    batch = get_object_or_404(UploadBatch, pk=batch_id)
    qs = CHWRecord.objects.filter(batch=batch, is_active=True, supervised=False)
    if county:     qs = qs.filter(county=county)
    if sub_county: qs = qs.filter(sub_county=sub_county)
    if chu:        qs = qs.filter(community_health_unit=chu)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="unsupervised_chps_{batch.label}.csv"'

    writer = csv.writer(response)
    writer.writerow(['County', 'Sub-County', 'Community Health Unit', 'CHP Area',
                     'CHP Name', 'CHP ID', 'HH Visits', 'Days Synced', 'Supervision Visits'])
    for r in qs.order_by('county', 'sub_county', 'community_health_unit'):
        writer.writerow([r.county, r.sub_county, r.community_health_unit, r.chp_area,
                         r.chw_name, r.chw_id, r.hh_visits, r.days_synced, r.supervision_visits])
    return response


@login_required
def download_low_performers(request):
    batch_id    = request.GET.get('batch')
    county      = request.GET.get('county', '')
    sub_county  = request.GET.get('sub_county', '')
    chu         = request.GET.get('chu', '')
    group       = request.GET.get('group', 'unsupervised')

    batch     = get_object_or_404(UploadBatch, pk=batch_id)
    threshold = 50 if batch.period_type == 'monthly' else 12
    qs = CHWRecord.objects.filter(batch=batch, is_active=True, hh_visits__lt=threshold)
    if group == 'supervised':
        qs = qs.filter(supervised=True)
    else:
        qs = qs.filter(supervised=False)
    if county:     qs = qs.filter(county=county)
    if sub_county: qs = qs.filter(sub_county=sub_county)
    if chu:        qs = qs.filter(community_health_unit=chu)

    label = 'low_performers_supervised' if group == 'supervised' else 'low_performers_not_supervised'
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{label}_{batch.label}.csv"'

    writer = csv.writer(response)
    writer.writerow(['County', 'Sub-County', 'Community Health Unit', 'CHP Area',
                     'CHP Name', 'CHP ID', 'HH Visits', 'Days Synced',
                     'Supervision Visits', f'Threshold (<{threshold})'])
    for r in qs.order_by('hh_visits', 'community_health_unit'):
        writer.writerow([r.county, r.sub_county, r.community_health_unit, r.chp_area,
                         r.chw_name, r.chw_id, r.hh_visits, r.days_synced,
                         r.supervision_visits, threshold])
    return response


@login_required
def download_anc_gap(request):
    from django.db.models import F as DjangoF
    batch_id    = request.GET.get('batch')
    county      = request.GET.get('county', '')
    sub_county  = request.GET.get('sub_county', '')
    chu         = request.GET.get('chu', '')

    batch = get_object_or_404(UploadBatch, pk=batch_id)
    qs = CHWRecord.objects.filter(batch=batch, is_active=True)
    if county:     qs = qs.filter(county=county)
    if sub_county: qs = qs.filter(sub_county=sub_county)
    if chu:        qs = qs.filter(community_health_unit=chu)
    qs = qs.exclude(active_pregnancies=0).filter(
        active_pregnancies__gt=DjangoF('pregnancies_visited')
    ).order_by('community_health_unit', 'chw_name')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="anc_gap_{batch.label}.csv"'

    writer = csv.writer(response)
    writer.writerow(['County', 'Sub-County', 'Community Health Unit', 'CHP Area',
                     'CHP Name', 'CHP ID', 'Active Pregnancies', 'Pregnancies Visited', 'Gap'])
    for r in qs:
        writer.writerow([r.county, r.sub_county, r.community_health_unit, r.chp_area,
                         r.chw_name, r.chw_id, r.active_pregnancies,
                         r.pregnancies_visited, r.active_pregnancies - r.pregnancies_visited])
    return response


@login_required
def download_same_day_flags(request):
    batch_id    = request.GET.get('batch')
    county      = request.GET.get('county', '')
    sub_county  = request.GET.get('sub_county', '')
    chu         = request.GET.get('chu', '')

    batch = get_object_or_404(UploadBatch, pk=batch_id)
    qs = SupervisionRecord.objects.filter(batch=batch)
    if county:     qs = qs.filter(county=county)
    if sub_county: qs = qs.filter(sub_county=sub_county)
    if chu:        qs = qs.filter(community_health_unit=chu)

    flags = (
        qs.values('county', 'sub_county', 'community_health_unit', 'visit_date')
        .annotate(count=Count('id'))
        .filter(count__gte=5)
        .order_by('-count')
    )

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="same_day_flags_{batch.label}.csv"'

    writer = csv.writer(response)
    writer.writerow(['County', 'Sub-County', 'Community Health Unit', 'Visit Date', 'Supervisions Count'])
    for f in flags:
        writer.writerow([f['county'], f['sub_county'], f['community_health_unit'],
                         f['visit_date'], f['count']])
    return response


# ===========================================================================
# SYNC DASHBOARD VIEWS
# ===========================================================================

from .models import SyncUploadBatch, CHPSyncRecord
from .parsers import parse_sync_file, compute_sync_indicators

forms = django_forms  # alias so SyncUploadForm reads cleanly


class SyncUploadForm(django_forms.ModelForm):
    year  = django_forms.ChoiceField(choices=[(y, y) for y in range(2024, 2028)], initial=2026)
    month = django_forms.ChoiceField(choices=[(i, m) for i, m in [
        (1,'January'),(2,'February'),(3,'March'),(4,'April'),(5,'May'),(6,'June'),
        (7,'July'),(8,'August'),(9,'September'),(10,'October'),(11,'November'),(12,'December')
    ]])
    period_type = django_forms.ChoiceField(
        choices=[('monthly','Monthly'),('weekly','Weekly')],
        widget=django_forms.RadioSelect,
    )
    week_start_date = django_forms.DateField(
        required=False,
        widget=django_forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
    )
    sync_file = django_forms.FileField(
        label='CHP Sync Report File (.xlsx)',
        widget=django_forms.FileInput(attrs={'accept': '.xlsx'}),
    )
    notes = django_forms.CharField(
        required=False,
        widget=django_forms.Textarea(attrs={'class': 'form-input', 'rows': 2}),
    )

    class Meta:
        model  = SyncUploadBatch
        fields = ['period_type', 'year', 'month', 'week_start_date', 'sync_file', 'notes']

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('period_type') == 'weekly' and not cleaned.get('week_start_date'):
            self.add_error('week_start_date', 'Week start date is required for weekly uploads.')
        return cleaned


# Need to import forms here


@login_required
@user_passes_test(is_uploader)
def sync_upload_view(request):
    form = SyncUploadForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        batch = form.save(commit=False)
        batch.uploaded_by = request.user
        batch.year  = int(form.cleaned_data['year'])
        batch.month = int(form.cleaned_data['month'])
        batch.save()

        rows, errors = parse_sync_file(batch, request.FILES['sync_file'])
        if errors:
            messages.warning(request, f"Upload completed with {len(errors)} warnings. {rows} rows saved.")
        else:
            messages.success(request, f"Sync report uploaded successfully! {rows} CHP records saved for {batch.label}.")
        return redirect('sync_dashboard')

    batches = SyncUploadBatch.objects.all().order_by('-year', '-month', '-week_start_date')
    return render(request, 'dashboard/sync_upload.html', {
        'form': form,
        'batches': batches,
        'is_uploader': True,
    })


@login_required
@user_passes_test(is_uploader)
def sync_delete_batch_view(request, pk):
    batch = get_object_or_404(SyncUploadBatch, pk=pk)
    if request.method == 'POST':
        label = batch.label
        batch.delete()
        messages.success(request, f"Sync batch '{label}' deleted.")
    return redirect('sync_upload')


def sync_dashboard_view(request):
    batches = SyncUploadBatch.objects.all()
    selected_batch_id  = request.GET.get('batch', '')
    selected_county    = request.GET.get('county', '')
    selected_subcounty = request.GET.get('sub_county', '')
    selected_chu       = request.GET.get('chu', '')

    selected_batch = None
    indicators     = None
    filter_options = {}

    if selected_batch_id:
        selected_batch = get_object_or_404(SyncUploadBatch, pk=selected_batch_id)
        qs = CHPSyncRecord.objects.filter(batch=selected_batch)

        filter_options['counties'] = qs.values_list('county', flat=True).distinct().order_by('county')

        if selected_county:
            qs = qs.filter(county=selected_county)
            filter_options['sub_counties'] = qs.values_list('sub_county', flat=True).distinct().order_by('sub_county')

        if selected_subcounty:
            qs = qs.filter(sub_county=selected_subcounty)
            filter_options['chus'] = qs.values_list('community_health_unit', flat=True).distinct().order_by('community_health_unit')

        if selected_chu:
            qs = qs.filter(community_health_unit=selected_chu)

        indicators = compute_sync_indicators(qs)

    import json
    chu_data_json = json.dumps(indicators['chus_sorted'] if indicators else [])

    return render(request, 'dashboard/sync_dashboard.html', {
        'batches':            batches,
        'selected_batch':     selected_batch,
        'selected_batch_id':  selected_batch_id,
        'selected_county':    selected_county,
        'selected_subcounty': selected_subcounty,
        'selected_chu':       selected_chu,
        'filter_options':     filter_options,
        'indicators':         indicators,
        'chu_data_json':      chu_data_json,
        'show_county_table':  not selected_county,
        'show_sc_table':      bool(selected_county and not selected_subcounty),
        'show_chu_chart':     bool(selected_subcounty),
        'is_uploader':        is_uploader(request.user) if request.user.is_authenticated else False,
    })


@require_GET
def api_never_synced(request):
    batch_id    = request.GET.get('batch')
    county      = request.GET.get('county', '')
    sub_county  = request.GET.get('sub_county', '')
    chu         = request.GET.get('chu', '')

    if not batch_id:
        return JsonResponse({'error': 'batch required'}, status=400)

    qs = CHPSyncRecord.objects.filter(batch_id=batch_id, days_synced=0)
    if county:     qs = qs.filter(county=county)
    if sub_county: qs = qs.filter(sub_county=sub_county)
    if chu:        qs = qs.filter(community_health_unit=chu)

    data = list(qs.values(
        'county', 'sub_county', 'community_health_unit',
        'chp_name', 'username', 'reports_synced', 'last_sync_date'
    ).order_by('sub_county', 'community_health_unit', 'chp_name'))

    for row in data:
        row['last_sync_date'] = str(row['last_sync_date']) if row['last_sync_date'] else 'Never'

    return JsonResponse({'results': data, 'count': len(data)})


@login_required
def download_never_synced(request):
    batch_id    = request.GET.get('batch')
    county      = request.GET.get('county', '')
    sub_county  = request.GET.get('sub_county', '')
    chu         = request.GET.get('chu', '')

    batch = get_object_or_404(SyncUploadBatch, pk=batch_id)
    qs = CHPSyncRecord.objects.filter(batch=batch, days_synced=0)
    if county:     qs = qs.filter(county=county)
    if sub_county: qs = qs.filter(sub_county=sub_county)
    if chu:        qs = qs.filter(community_health_unit=chu)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="never_synced_{batch.label}.csv"'
    writer = csv.writer(response)
    writer.writerow(['County', 'Sub-County', 'Community Health Unit', 'CHP Name', 'Username', 'Days Synced', 'Reports Synced', 'Last Sync Date'])
    for r in qs.order_by('sub_county', 'community_health_unit', 'chp_name'):
        writer.writerow([r.county, r.sub_county, r.community_health_unit,
                         r.chp_name, r.username, r.days_synced, r.reports_synced,
                         r.last_sync_date or 'Never'])
    return response


@login_required
def download_chu_sync(request):
    batch_id    = request.GET.get('batch')
    county      = request.GET.get('county', '')
    sub_county  = request.GET.get('sub_county', '')
    chu         = request.GET.get('chu', '')

    from django.db.models import Count, Avg, Q

    batch = get_object_or_404(SyncUploadBatch, pk=batch_id)
    qs = CHPSyncRecord.objects.filter(batch=batch)
    if county:     qs = qs.filter(county=county)
    if sub_county: qs = qs.filter(sub_county=sub_county)
    if chu:        qs = qs.filter(community_health_unit=chu)

    chu_data = (
        qs.values('county', 'sub_county', 'community_health_unit')
        .annotate(
            total=Count('id'),
            synced=Count('id', filter=Q(days_synced__gte=1)),
            never=Count('id', filter=Q(days_synced=0)),
            avg_days=Avg('days_synced'),
            avg_reports=Avg('reports_synced'),
        )
        .order_by('sub_county', 'community_health_unit')
    )

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="chu_sync_{batch.label}.csv"'
    writer = csv.writer(response)
    writer.writerow(['County', 'Sub-County', 'Community Health Unit', 'Total CHPs',
                     'Synced', 'Never Synced', 'Sync Rate %', 'Avg Days Synced', 'Avg Reports Synced'])
    for c in chu_data:
        t = c['total'] or 1
        writer.writerow([
            c['county'], c['sub_county'], c['community_health_unit'],
            c['total'], c['synced'], c['never'],
            round(c['synced'] / t * 100, 1),
            round(c['avg_days'] or 0, 2),
            round(c['avg_reports'] or 0, 1),
        ])
    return response