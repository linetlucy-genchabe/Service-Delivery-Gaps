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
            batch.week_end_date = form.cleaned_data.get('week_end_date')
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
def api_inactive_chps(request):
    """Inactive CHPs for the selected batch."""
    batch_id   = request.GET.get('batch')
    county     = request.GET.get('county', '')
    sub_county = request.GET.get('sub_county', '')
    chu        = request.GET.get('chu', '')

    if not batch_id:
        return JsonResponse({'error': 'batch required'}, status=400)

    qs = CHWRecord.objects.filter(batch_id=batch_id, is_active=False)
    if county:     qs = qs.filter(county=county)
    if sub_county: qs = qs.filter(sub_county=sub_county)
    if chu:        qs = qs.filter(community_health_unit=chu)

    data = list(qs.values(
        'county', 'sub_county', 'community_health_unit', 'chp_area', 'chw_name'
    ).order_by('county', 'sub_county', 'community_health_unit', 'chw_name'))

    return JsonResponse({'results': data, 'count': len(data)})


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

    # CHPs with active pregnancies but zero visits
    qs = qs.filter(active_pregnancies__gt=0, pregnancies_visited=0)

    data = list(qs.values(
        'county', 'sub_county', 'community_health_unit', 'chp_area',
        'chw_name', 'active_pregnancies', 'pregnancies_visited'
    ).order_by('community_health_unit', 'chw_name'))

    for row in data:
        row['gap'] = row['active_pregnancies']  # all unvisited since visited=0

    return JsonResponse({'results': data, 'count': len(data)})


@login_required
@require_GET
def api_supervised_3plus(request):
    """CHPs who received 3 or more supervision visits — data quality flag."""
    batch_id   = request.GET.get('batch')
    county     = request.GET.get('county', '')
    sub_county = request.GET.get('sub_county', '')
    chu        = request.GET.get('chu', '')

    if not batch_id:
        return JsonResponse({'error': 'batch required'}, status=400)

    qs = CHWRecord.objects.filter(batch_id=batch_id, is_active=True, supervision_visits__gte=3)
    if county:     qs = qs.filter(county=county)
    if sub_county: qs = qs.filter(sub_county=sub_county)
    if chu:        qs = qs.filter(community_health_unit=chu)

    data = list(qs.values(
        'county', 'sub_county', 'community_health_unit', 'chp_area',
        'chw_name', 'hh_visits', 'supervision_visits'
    ).order_by('-supervision_visits', 'community_health_unit'))

    return JsonResponse({'results': data, 'count': len(data)})


@login_required
@require_GET
def api_u5_gap(request):
    """U5 assessment gap drill-downs."""
    batch_id   = request.GET.get('batch')
    county     = request.GET.get('county', '')
    sub_county = request.GET.get('sub_county', '')
    chu        = request.GET.get('chu', '')
    gap_type   = request.GET.get('type', 'high_hh_low_u5')  # or 'high_u5_low_pos'

    if not batch_id:
        return JsonResponse({'error': 'batch required'}, status=400)

    qs = CHWRecord.objects.filter(
        batch_id=batch_id, is_active=True,
        registered_hhs__gt=0, registered_children_u5__gt=0
    )
    if county:     qs = qs.filter(county=county)
    if sub_county: qs = qs.filter(sub_county=sub_county)
    if chu:        qs = qs.filter(community_health_unit=chu)

    rows = list(qs.values(
        'county', 'sub_county', 'community_health_unit', 'chp_area',
        'chw_name', 'registered_hhs', 'hh_visits',
        'registered_children_u5', 'num_u5_assessed', 'positive_diagnoses_u5', 'iccm_assessments'
    ))

    results = []
    for r in rows:
        hh_rate  = r['hh_visits'] / r['registered_hhs'] if r['registered_hhs'] else 0
        u5_rate  = r['num_u5_assessed'] / r['registered_children_u5'] if r['registered_children_u5'] else 0
        r['hh_rate_pct']  = round(hh_rate * 100, 1)
        r['u5_rate_pct']  = round(u5_rate * 100, 1)

        if gap_type == 'high_hh_low_u5' and hh_rate >= 0.7 and u5_rate < 0.4:
            results.append(r)
        elif gap_type == 'high_u5_low_pos' and u5_rate >= 0.8 and r['num_u5_assessed'] >= 10 and r['positive_diagnoses_u5'] == 0:
            results.append(r)

    results.sort(key=lambda x: x['u5_rate_pct'])
    return JsonResponse({'results': results, 'count': len(results)})


@login_required
@require_GET
def api_zero_pregnancies(request):
    """Active CHPs with zero active pregnancies registered."""
    batch_id   = request.GET.get('batch')
    county     = request.GET.get('county', '')
    sub_county = request.GET.get('sub_county', '')
    chu        = request.GET.get('chu', '')

    if not batch_id:
        return JsonResponse({'error': 'batch required'}, status=400)

    qs = CHWRecord.objects.filter(batch_id=batch_id, is_active=True, active_pregnancies=0)
    if county:     qs = qs.filter(county=county)
    if sub_county: qs = qs.filter(sub_county=sub_county)
    if chu:        qs = qs.filter(community_health_unit=chu)

    data = list(qs.values(
        'county', 'sub_county', 'community_health_unit', 'chp_area',
        'chw_name', 'hh_visits', 'pregnancies_registered', 'active_pregnancies'
    ).order_by('community_health_unit', 'chw_name'))

    return JsonResponse({'results': data, 'count': len(data)})


@login_required
def download_zero_pregnancies(request):
    batch_id   = request.GET.get('batch')
    county     = request.GET.get('county', '')
    sub_county = request.GET.get('sub_county', '')
    chu        = request.GET.get('chu', '')

    batch = get_object_or_404(UploadBatch, pk=batch_id)
    qs = CHWRecord.objects.filter(batch=batch, is_active=True, active_pregnancies=0)
    if county:     qs = qs.filter(county=county)
    if sub_county: qs = qs.filter(sub_county=sub_county)
    if chu:        qs = qs.filter(community_health_unit=chu)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="zero_active_pregnancies_{batch.label}.csv"'
    writer = csv.writer(response)
    writer.writerow(['County', 'Sub-County', 'Community Health Unit', 'CHP Area',
                     'CHP Name', 'HH Visits', 'Pregnancies Registered', 'Active Pregnancies'])
    for r in qs.order_by('community_health_unit', 'chw_name'):
        writer.writerow([r.county, r.sub_county, r.community_health_unit, r.chp_area,
                         r.chw_name, r.hh_visits, r.pregnancies_registered, r.active_pregnancies])
    return response


@login_required
@require_GET
def api_zero_positive(request):
    """Active CHPs with zero positive diagnoses U5."""
    batch_id   = request.GET.get('batch')
    county     = request.GET.get('county', '')
    sub_county = request.GET.get('sub_county', '')
    chu        = request.GET.get('chu', '')

    if not batch_id:
        return JsonResponse({'error': 'batch required'}, status=400)

    qs = CHWRecord.objects.filter(batch_id=batch_id, is_active=True, positive_diagnoses_u5=0)
    if county:     qs = qs.filter(county=county)
    if sub_county: qs = qs.filter(sub_county=sub_county)
    if chu:        qs = qs.filter(community_health_unit=chu)

    data = list(qs.values(
        'county', 'sub_county', 'community_health_unit', 'chp_area',
        'chw_name', 'hh_visits', 'num_u5_assessed',
        'iccm_assessments', 'positive_diagnoses_u5'
    ).order_by('community_health_unit', 'chw_name'))

    return JsonResponse({'results': data, 'count': len(data)})


@login_required
def download_zero_positive(request):
    batch_id   = request.GET.get('batch')
    county     = request.GET.get('county', '')
    sub_county = request.GET.get('sub_county', '')
    chu        = request.GET.get('chu', '')

    batch = get_object_or_404(UploadBatch, pk=batch_id)
    qs = CHWRecord.objects.filter(batch=batch, is_active=True, positive_diagnoses_u5=0)
    if county:     qs = qs.filter(county=county)
    if sub_county: qs = qs.filter(sub_county=sub_county)
    if chu:        qs = qs.filter(community_health_unit=chu)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="zero_positive_diagnoses_{batch.label}.csv"'
    writer = csv.writer(response)
    writer.writerow(['County', 'Sub-County', 'Community Health Unit', 'CHP Area',
                     'CHP Name', 'HH Visits', 'U5 Assessed', 'iCCM Assessments', 'Positive Diagnoses'])
    for r in qs.order_by('community_health_unit', 'chw_name'):
        writer.writerow([r.county, r.sub_county, r.community_health_unit, r.chp_area,
                         r.chw_name, r.hh_visits, r.num_u5_assessed,
                         r.iccm_assessments, r.positive_diagnoses_u5])
    return response


@login_required
@require_GET
def api_low_iccm(request):
    """Active CHPs with fewer than 5 iCCM assessments."""
    batch_id   = request.GET.get('batch')
    county     = request.GET.get('county', '')
    sub_county = request.GET.get('sub_county', '')
    chu        = request.GET.get('chu', '')

    if not batch_id:
        return JsonResponse({'error': 'batch required'}, status=400)

    qs = CHWRecord.objects.filter(batch_id=batch_id, is_active=True, iccm_assessments__lt=5)
    if county:     qs = qs.filter(county=county)
    if sub_county: qs = qs.filter(sub_county=sub_county)
    if chu:        qs = qs.filter(community_health_unit=chu)

    data = list(qs.values(
        'county', 'sub_county', 'community_health_unit', 'chp_area',
        'chw_name', 'hh_visits', 'iccm_assessments',
        'registered_children_u5', 'num_u5_assessed'
    ).order_by('iccm_assessments', 'community_health_unit'))

    return JsonResponse({'results': data, 'count': len(data)})


@login_required
def download_low_iccm(request):
    batch_id   = request.GET.get('batch')
    county     = request.GET.get('county', '')
    sub_county = request.GET.get('sub_county', '')
    chu        = request.GET.get('chu', '')

    batch = get_object_or_404(UploadBatch, pk=batch_id)
    qs = CHWRecord.objects.filter(batch=batch, is_active=True, iccm_assessments__lt=5)
    if county:     qs = qs.filter(county=county)
    if sub_county: qs = qs.filter(sub_county=sub_county)
    if chu:        qs = qs.filter(community_health_unit=chu)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="low_iccm_assessments_{batch.label}.csv"'
    writer = csv.writer(response)
    writer.writerow(['County', 'Sub-County', 'Community Health Unit', 'CHP Area',
                     'CHP Name', 'HH Visits', 'iCCM Assessments',
                     'Registered U5', 'U5 Assessed'])
    for r in qs.order_by('iccm_assessments', 'community_health_unit'):
        writer.writerow([r.county, r.sub_county, r.community_health_unit, r.chp_area,
                         r.chw_name, r.hh_visits, r.iccm_assessments,
                         r.registered_children_u5, r.num_u5_assessed])
    return response


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
    qs = qs.filter(active_pregnancies__gt=0, pregnancies_visited=0
    ).order_by('community_health_unit', 'chw_name')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="anc_gap_zero_visits_{batch.label}.csv"'

    writer = csv.writer(response)
    writer.writerow(['County', 'Sub-County', 'Community Health Unit', 'CHP Area',
                     'CHP Name', 'Active Pregnancies', 'Pregnancies Visited'])
    for r in qs:
        writer.writerow([r.county, r.sub_county, r.community_health_unit, r.chp_area,
                         r.chw_name, r.active_pregnancies, r.pregnancies_visited])
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


@login_required
def download_u5_gap(request):
    from django.db.models import F as DjangoF
    batch_id   = request.GET.get('batch')
    county     = request.GET.get('county', '')
    sub_county = request.GET.get('sub_county', '')
    chu        = request.GET.get('chu', '')
    gap_type   = request.GET.get('type', 'high_hh_low_u5')

    batch = get_object_or_404(UploadBatch, pk=batch_id)
    qs = CHWRecord.objects.filter(
        batch=batch, is_active=True,
        registered_hhs__gt=0, registered_children_u5__gt=0
    )
    if county:     qs = qs.filter(county=county)
    if sub_county: qs = qs.filter(sub_county=sub_county)
    if chu:        qs = qs.filter(community_health_unit=chu)

    rows = list(qs.values(
        'county', 'sub_county', 'community_health_unit', 'chp_area',
        'chw_name', 'registered_hhs', 'hh_visits',
        'registered_children_u5', 'num_u5_assessed', 'positive_diagnoses_u5'
    ))

    results = []
    for r in rows:
        hh_rate = r['hh_visits'] / r['registered_hhs'] if r['registered_hhs'] else 0
        u5_rate = r['num_u5_assessed'] / r['registered_children_u5'] if r['registered_children_u5'] else 0
        r['hh_rate_pct'] = round(hh_rate * 100, 1)
        r['u5_rate_pct'] = round(u5_rate * 100, 1)
        if gap_type == 'high_hh_low_u5' and hh_rate >= 0.7 and u5_rate < 0.4:
            results.append(r)
        elif gap_type == 'high_u5_low_pos' and u5_rate >= 0.8 and r['num_u5_assessed'] >= 10 and r['positive_diagnoses_u5'] == 0:
            results.append(r)

    if gap_type == 'high_hh_low_u5':
        filename = f'good_hh_low_u5_assessment_{batch.label}.csv'
        headers  = ['County', 'Sub-County', 'Community Health Unit', 'CHP Area', 'CHP Name',
                    'Registered HHs', 'HH Visits', 'HH Rate %',
                    'Registered U5', 'U5 Assessed', 'U5 Assessment Rate %']
    else:
        filename = f'high_u5_zero_positive_diagnoses_{batch.label}.csv'
        headers  = ['County', 'Sub-County', 'Community Health Unit', 'CHP Area', 'CHP Name',
                    'Registered U5', 'U5 Assessed', 'U5 Assessment Rate %', 'Positive Diagnoses']

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(headers)

    for r in sorted(results, key=lambda x: x['u5_rate_pct']):
        if gap_type == 'high_hh_low_u5':
            writer.writerow([r['county'], r['sub_county'], r['community_health_unit'], r['chp_area'],
                             r['chw_name'], r['registered_hhs'], r['hh_visits'], r['hh_rate_pct'],
                             r['registered_children_u5'], r['num_u5_assessed'], r['u5_rate_pct']])
        else:
            writer.writerow([r['county'], r['sub_county'], r['community_health_unit'], r['chp_area'],
                             r['chw_name'], r['registered_children_u5'], r['num_u5_assessed'],
                             r['u5_rate_pct'], r['positive_diagnoses_u5']])
    return response


@login_required
def download_supervised_3plus(request):
    batch_id   = request.GET.get('batch')
    county     = request.GET.get('county', '')
    sub_county = request.GET.get('sub_county', '')
    chu        = request.GET.get('chu', '')

    batch = get_object_or_404(UploadBatch, pk=batch_id)
    qs = CHWRecord.objects.filter(batch=batch, is_active=True, supervision_visits__gte=3)
    if county:     qs = qs.filter(county=county)
    if sub_county: qs = qs.filter(sub_county=sub_county)
    if chu:        qs = qs.filter(community_health_unit=chu)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="supervised_3plus_{batch.label}.csv"'
    writer = csv.writer(response)
    writer.writerow(['County', 'Sub-County', 'Community Health Unit', 'CHP Area',
                     'CHP Name', 'HH Visits', 'Supervision Visits'])
    for r in qs.order_by('-supervision_visits', 'community_health_unit'):
        writer.writerow([r.county, r.sub_county, r.community_health_unit, r.chp_area,
                         r.chw_name, r.hh_visits, r.supervision_visits])
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
        label='Week Start Date',
        help_text='First day of the reporting period',
    )
    week_end_date = django_forms.DateField(
        required=False,
        widget=django_forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        label='Week End Date (optional)',
        help_text='Last day of the reporting period. Leave blank for standard week label.',
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
        batch.week_end_date = form.cleaned_data.get('week_end_date')
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
        qs = CHPSyncRecord.objects.filter(batch=selected_batch).exclude(
            county='').exclude(sub_county='').exclude(community_health_unit='')

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
    chu_data_json    = json.dumps(indicators['chus_sorted'] if indicators else [])
    county_data_json = json.dumps(indicators['counties']    if indicators else [])
    sc_data_json     = json.dumps(indicators['sub_counties'] if indicators else [])

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
        'county_data_json':   county_data_json,
        'sc_data_json':       sc_data_json,
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

    qs = CHPSyncRecord.objects.filter(batch_id=batch_id, days_synced=0).exclude(
        county='').exclude(sub_county='').exclude(community_health_unit='')
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
    qs = CHPSyncRecord.objects.filter(batch=batch, days_synced=0).exclude(
        county='').exclude(sub_county='').exclude(community_health_unit='')
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


# ===========================================================================
# SYNC COMPARISON VIEW
# ===========================================================================

def sync_compare_view(request):
    """Compare 2-4 sync batches with 5-category classification."""
    batches    = SyncUploadBatch.objects.all().order_by('-year', '-month', '-week_start_date')
    county     = request.GET.get('county', '')
    sub_county = request.GET.get('sub_county', '')
    chu        = request.GET.get('chu', '')

    # Collect up to 4 batch IDs
    batch_ids = []
    for key in ['batch_a', 'batch_b', 'batch_c', 'batch_d']:
        val = request.GET.get(key, '').strip()
        if val and val not in batch_ids:
            batch_ids.append(val)

    comparison  = None
    filter_opts = {}
    selected_batch_ids = {
        'batch_a': request.GET.get('batch_a', ''),
        'batch_b': request.GET.get('batch_b', ''),
        'batch_c': request.GET.get('batch_c', ''),
        'batch_d': request.GET.get('batch_d', ''),
    }

    if len(batch_ids) >= 2:
        selected_batches = [get_object_or_404(SyncUploadBatch, pk=bid) for bid in batch_ids]
        n = len(selected_batches)

        def base_qs(batch):
            qs = CHPSyncRecord.objects.filter(batch=batch).exclude(
                county='').exclude(sub_county='').exclude(community_health_unit='')
            if county:     qs = qs.filter(county=county)
            if sub_county: qs = qs.filter(sub_county=sub_county)
            if chu:        qs = qs.filter(community_health_unit=chu)
            return qs

        def to_dict(qs):
            return {r['username']: r for r in qs.values(
                'username', 'chp_name', 'county', 'sub_county',
                'community_health_unit', 'days_synced', 'last_sync_date'
            )}

        dicts = [to_dict(base_qs(b)) for b in selected_batches]
        all_usernames = set()
        for d in dicts:
            all_usernames |= set(d.keys())

        # Labels for each batch column
        labels = [b.label for b in selected_batches]

        # 5 categories based on sync count across all batches
        synced_all   = []  # synced in every batch
        synced_most  = []  # synced in more than half but not all
        synced_some  = []  # synced in at least one but <= half
        never_synced = []  # never synced in any batch
        appeared_dropped = []  # only in one batch (new or dropped)

        for username in sorted(all_usernames):
            records = [d.get(username) for d in dicts]
            ref = next(r for r in records if r is not None)

            synced_flags = [bool(r and r['days_synced'] >= 1) for r in records]
            synced_count = sum(synced_flags)

            row = {
                'username':              username,
                'chp_name':              ref['chp_name'],
                'county':                ref['county'],
                'sub_county':            ref['sub_county'],
                'community_health_unit': ref['community_health_unit'],
                'synced_flags':          synced_flags,
                'synced_count':          synced_count,
                'days':  [r['days_synced'] if r else '—' for r in records],
                'dates': [str(r['last_sync_date']) if r and r['last_sync_date'] else 'Never' for r in records],
            }

            if synced_count == n:
                synced_all.append(row)
            elif synced_count == 0:
                never_synced.append(row)
            elif synced_count == 1:
                appeared_dropped.append(row)
            elif synced_count > n / 2:
                synced_most.append(row)
            else:
                synced_some.append(row)

        # Filter options
        filter_qs = CHPSyncRecord.objects.filter(batch=selected_batches[0]).exclude(
            county='').exclude(sub_county='').exclude(community_health_unit='')
        filter_opts['counties'] = filter_qs.values_list('county', flat=True).distinct().order_by('county')
        if county:
            filter_opts['sub_counties'] = filter_qs.filter(county=county).values_list('sub_county', flat=True).distinct().order_by('sub_county')
        if sub_county:
            filter_opts['chus'] = filter_qs.filter(county=county, sub_county=sub_county).values_list('community_health_unit', flat=True).distinct().order_by('community_health_unit')

        total = len(all_usernames)
        comparison = {
            'batches':          selected_batches,
            'labels':           labels,
            'n':                n,
            'total':            total,
            'synced_all':       synced_all,
            'synced_most':      synced_most,
            'synced_some':      synced_some,
            'never_synced':     never_synced,
            'appeared_dropped': appeared_dropped,
            'count_all':        len(synced_all),
            'count_most':       len(synced_most),
            'count_some':       len(synced_some),
            'count_never':      len(never_synced),
            'count_appeared':   len(appeared_dropped),
        }

    return render(request, 'dashboard/sync_compare.html', {
        'batches':          batches,
        'selected_batch_ids': selected_batch_ids,
        'comparison':       comparison,
        'filter_opts':      filter_opts,
        'selected_county':    county,
        'selected_subcounty': sub_county,
        'selected_chu':       chu,
        'is_uploader': is_uploader(request.user) if request.user.is_authenticated else False,
    })


@require_GET
def api_compare_download(request):
    """CSV download for any comparison category — supports 2-4 batches."""
    category   = request.GET.get('category', 'never_synced')
    county     = request.GET.get('county', '')
    sub_county = request.GET.get('sub_county', '')
    chu        = request.GET.get('chu', '')

    batch_ids = []
    for key in ['batch_a', 'batch_b', 'batch_c', 'batch_d']:
        val = request.GET.get(key, '').strip()
        if val and val not in batch_ids:
            batch_ids.append(val)

    if len(batch_ids) < 2:
        return HttpResponse('Need at least 2 batches', status=400)

    selected_batches = [get_object_or_404(SyncUploadBatch, pk=bid) for bid in batch_ids]
    n = len(selected_batches)

    def base_qs(batch):
        qs = CHPSyncRecord.objects.filter(batch=batch).exclude(
            county='').exclude(sub_county='').exclude(community_health_unit='')
        if county:     qs = qs.filter(county=county)
        if sub_county: qs = qs.filter(sub_county=sub_county)
        if chu:        qs = qs.filter(community_health_unit=chu)
        return qs

    dicts = [{r['username']: r for r in base_qs(b).values(
        'username', 'chp_name', 'county', 'sub_county',
        'community_health_unit', 'days_synced', 'last_sync_date'
    )} for b in selected_batches]

    all_usernames = set()
    for d in dicts:
        all_usernames |= set(d.keys())

    rows = []
    for username in sorted(all_usernames):
        records = [d.get(username) for d in dicts]
        ref = next(r for r in records if r is not None)
        synced_count = sum(1 for r in records if r and r['days_synced'] >= 1)

        include = False
        if category == 'synced_all'       and synced_count == n: include = True
        elif category == 'synced_most'    and synced_count > n/2 and synced_count < n: include = True
        elif category == 'synced_some'    and 0 < synced_count <= n/2 and synced_count > 1: include = True
        elif category == 'never_synced'   and synced_count == 0: include = True
        elif category == 'appeared_dropped' and synced_count == 1: include = True

        if include:
            rows.append({
                'username': username,
                'chp_name': ref['chp_name'],
                'county': ref['county'],
                'sub_county': ref['sub_county'],
                'community_health_unit': ref['community_health_unit'],
                'days': [r['days_synced'] if r else '—' for r in records],
                'dates': [str(r['last_sync_date']) if r and r['last_sync_date'] else 'Never' for r in records],
            })

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="sync_compare_{category}.csv"'
    writer = csv.writer(response)

    header = ['County', 'Sub-County', 'Community Health Unit', 'CHP Name', 'Username']
    for b in selected_batches:
        header += [f'Days Synced ({b.label})', f'Last Sync ({b.label})']
    writer.writerow(header)

    for r in rows:
        row = [r['county'], r['sub_county'], r['community_health_unit'], r['chp_name'], r['username']]
        for days, date in zip(r['days'], r['dates']):
            row += [days, date]
        writer.writerow(row)

    return response


# ===========================================================================
# WEEKLY PERFORMANCE SCORECARD
# ===========================================================================

# Hardcoded targets (universal across all counties/sub-counties/CHUs)
SCORECARD_TARGETS = {
    'active_chps':            {'target': None, 'unit': '',  'label': 'Active CHPs',              'higher_is_better': True, 'type': 'active_chps'},
    'hh_coverage_pct':        {'target': 85,   'unit': '%', 'label': 'HH Coverage',               'higher_is_better': True, 'type': 'simple'},
    'child_health':           {'target': None, 'unit': '',  'label': 'Child Health Indicators',   'higher_is_better': True, 'type': 'child_health'},
    'iccm_referrals':         {'target': None, 'unit': '',  'label': 'iCCM Referrals',            'higher_is_better': True, 'type': 'simple'},
    'iccm_referral_pct':      {'target': 90,   'unit': '%', 'label': 'iCCM Referrals Completed',  'higher_is_better': True, 'type': 'iccm_ref'},
    'pnc_ontime_pct':         {'target': 85,   'unit': '%', 'label': 'On Time PNC',               'higher_is_better': True, 'type': 'pnc'},
    'preg_registered_chp':    {'target': 1,    'unit': '',  'label': 'Preg Registered/CHP',       'higher_is_better': True, 'type': 'simple'},
    'sync_rate_pct':          {'target': 80,   'unit': '%', 'label': '% CHPs Syncing Weekly',     'higher_is_better': True, 'type': 'simple'},
    'supervision_pct':        {'target': 65,   'unit': '%', 'label': '% CHPs Supervised',         'higher_is_better': True, 'type': 'simple'},
}


def compute_scorecard_metrics(chw_qs, sync_qs=None):
    """Compute all scorecard metrics from a CHWRecord queryset."""
    from django.db.models import Sum, Count, Avg, Q

    active_qs   = chw_qs.filter(is_active=True)
    total_active = active_qs.count()
    total_all    = chw_qs.count()

    if total_all == 0:
        return None

    # 1. Active CHPs %
    active_pct = round(total_active / total_all * 100, 1) if total_all else 0

    # 2. HH Coverage % — avg across CHPs with registered HHs
    hh_qs = active_qs.filter(registered_hhs__gt=0)
    hh_metrics = hh_qs.aggregate(
        total_visits=Sum('hh_visits'),
        total_registered=Sum('registered_hhs'),
    )
    hh_coverage = round(
        (hh_metrics['total_visits'] or 0) / (hh_metrics['total_registered'] or 1) * 100, 1
    )

    # 3. Avg Positive Diagnoses per CHP
    pos_agg = active_qs.aggregate(total_pos=Sum('positive_diagnoses_u5'))
    avg_pos = round((pos_agg['total_pos'] or 0) / total_active, 2) if total_active else 0

    # 4. On Time PNC % = sum(PNC 48hr) / sum(Total Deliveries)
    pnc_agg = active_qs.filter(total_deliveries__gt=0).aggregate(
        pnc=Sum('pnc_48hr_ontime'),
        del_total=Sum('total_deliveries'),
    )
    pnc_pct = round(
        (pnc_agg['pnc'] or 0) / (pnc_agg['del_total'] or 1) * 100, 1
    )

    # 5. Pregnancies Registered per CHP
    preg_agg = active_qs.aggregate(total_preg=Sum('pregnancies_registered'))
    preg_per_chp = round((preg_agg['total_preg'] or 0) / total_active, 2) if total_active else 0

    # 6. % CHPs Supervised
    # Use whichever signal gives a non-100% result — 100% always indicates a data issue
    supervised_bool   = active_qs.filter(supervised=True).count()
    supervised_visits = active_qs.filter(supervision_visits__gt=0).count()

    if supervised_bool == total_active:
        # All CHPs show as supervised — likely a supervised-only extract bug
        # Fall back to supervision_visits count
        supervised = supervised_visits
    elif supervised_visits > 0 and supervised_visits != total_active:
        # supervision_visits has real data — use the higher of the two as they should agree
        supervised = max(supervised_bool, supervised_visits)
    else:
        supervised = supervised_bool

    sup_pct = round(supervised / total_active * 100, 1) if total_active else 0

    # 7. Sync rate — from sync queryset if provided
    sync_pct = None
    if sync_qs is not None:
        total_sync = sync_qs.count()
        synced     = sync_qs.filter(days_synced__gte=1).count()
        sync_pct   = round(synced / total_sync * 100, 1) if total_sync else 0

    # 8. Child Health Indicators
    child_agg = active_qs.aggregate(
        total_u5_assessed=Sum('num_u5_assessed'),
        total_registered_u5=Sum('registered_children_u5'),
        total_iccm=Sum('iccm_assessments'),
        total_pos=Sum('positive_diagnoses_u5'),
        total_referrals=Sum('iccm_referrals_total'),
        total_referrals_completed=Sum('iccm_referral_followup'),
        total_fever_cases=Sum('fever_cases'),
        total_fever_tested=Sum('fever_tested_rdt'),
    )
    total_u5_assessed    = child_agg['total_u5_assessed'] or 0
    total_registered_u5  = child_agg['total_registered_u5'] or 0
    total_iccm           = child_agg['total_iccm'] or 0
    total_referrals      = child_agg['total_referrals'] or 0
    total_ref_completed  = child_agg['total_referrals_completed'] or 0
    total_fever_cases    = child_agg['total_fever_cases'] or 0
    total_fever_tested   = child_agg['total_fever_tested'] or 0

    u5_assessment_pct = round(total_u5_assessed / total_registered_u5 * 100, 1) if total_registered_u5 else 0
    iccm_referral_pct = round(total_ref_completed / total_referrals * 100, 1) if total_referrals else None
    avg_pos_diag      = round((child_agg['total_pos'] or 0) / total_active, 1) if total_active else 0

    # PNC numerator/denominator for display
    pnc_numerator   = pnc_agg['pnc'] or 0
    pnc_denominator = pnc_agg['del_total'] or 0

    # Active CHPs as % of total CHPs
    active_chps_pct = round(total_active / total_all * 100, 1) if total_all else 0

    return {
        'active_chps':         total_active,
        'total_chps':          total_all,
        'active_chps_pct':     active_chps_pct,
        'hh_coverage_pct':     hh_coverage,
        'hh_visits_total':     hh_metrics['total_visits'] or 0,
        'hh_registered_total': hh_metrics['total_registered'] or 0,
        'u5_assessment_pct':   u5_assessment_pct,
        'total_registered_u5': total_registered_u5,
        'total_u5_assessed':   total_u5_assessed,
        'iccm_assessments':    total_iccm,
        'avg_positive_diag':   avg_pos_diag,
        'total_positive_diag': child_agg['total_pos'] or 0,
        'fever_cases':         total_fever_cases,
        'fever_tested':        total_fever_tested,
        'iccm_referrals':      total_referrals,
        'iccm_referral_pct':   iccm_referral_pct,
        'iccm_ref_completed':  total_ref_completed,
        'pnc_ontime_pct':      pnc_pct,
        'pnc_numerator':       pnc_numerator,
        'pnc_denominator':     pnc_denominator,
        'preg_registered_chp': preg_per_chp,
        'supervision_pct':     sup_pct,
        'sync_rate_pct':       sync_pct,
    }


def get_colour(value, target, higher_is_better=True):
    """Return green/yellow/red based on % of target achieved. None target = no colour."""
    if value is None or target is None or target == 0:
        return 'grey'
    pct = value / target * 100 if higher_is_better else (2 * target - value) / target * 100
    if pct >= 100:   return 'green'
    if pct >= 50:    return 'yellow'
    return 'red'


def find_matching_sync_batch(chw_batch):
    """Find sync batch closest in time to a CHW batch."""
    if chw_batch is None:
        return None
    qs = SyncUploadBatch.objects.filter(
        year=chw_batch.year, month=chw_batch.month,
        period_type=chw_batch.period_type
    )
    if chw_batch.period_type == 'weekly' and chw_batch.week_start_date:
        # Prefer exact week match, then closest
        exact = qs.filter(week_start_date=chw_batch.week_start_date).first()
        if exact:
            return exact
    return qs.first()


def auto_detect_batches(county=None, sub_county=None, chu=None):
    """
    Auto-detect which CHW batches to use for each scorecard column.
    Returns dict with keys: prev_month, prev_week, current_week
    """
    from datetime import date
    import calendar

    all_batches = UploadBatch.objects.all().order_by('-year', '-month', '-week_start_date', '-uploaded_at')

    monthly  = list(all_batches.filter(period_type='monthly'))
    weekly   = list(all_batches.filter(period_type='weekly'))

    # Current week = most recent weekly batch
    current_week = weekly[0] if weekly else None

    # Previous week = second most recent weekly batch in same month
    prev_week = None
    if current_week:
        same_month_weekly = [b for b in weekly if b.year == current_week.year and b.month == current_week.month and b.pk != current_week.pk]
        prev_week = same_month_weekly[0] if same_month_weekly else None

    # Previous month = most recent monthly batch from a different month
    # OR most recent weekly batch from previous month
    prev_month = None
    if current_week:
        prev_monthly = [b for b in monthly if (b.year, b.month) < (current_week.year, current_week.month)]
        if prev_monthly:
            prev_month = prev_monthly[0]
        else:
            prev_weekly_other_month = [b for b in weekly if (b.year, b.month) < (current_week.year, current_week.month)]
            prev_month = prev_weekly_other_month[0] if prev_weekly_other_month else None

    return {
        'prev_month':   prev_month,
        'prev_week':    prev_week,
        'current_week': current_week,
    }


def scorecard_view(request):
    """Weekly performance scorecard view."""
    # Multi-select: getlist returns [] if nothing selected
    selected_counties    = request.GET.getlist('county')
    selected_subcounties = request.GET.getlist('sub_county')
    selected_chus        = request.GET.getlist('chu')

    # Manual override batch selectors
    override_prev_month   = request.GET.get('batch_prev_month', '')
    override_prev_week    = request.GET.get('batch_prev_week', '')
    override_current_week = request.GET.get('batch_current', '')

    all_batches = UploadBatch.objects.all().order_by('-year', '-month', '-week_start_date')

    # Auto-detect
    auto = auto_detect_batches()

    # Apply overrides
    def resolve_batch(override, auto_val):
        if override:
            return UploadBatch.objects.filter(pk=override).first()
        return auto_val

    batch_prev_month   = resolve_batch(override_prev_month,   auto['prev_month'])
    batch_prev_week    = resolve_batch(override_prev_week,    auto['prev_week'])
    batch_current_week = resolve_batch(override_current_week, auto['current_week'])

    def get_chw_qs(batch):
        if batch is None:
            return None
        qs = CHWRecord.objects.filter(batch=batch)
        if selected_counties:    qs = qs.filter(county__in=selected_counties)
        if selected_subcounties: qs = qs.filter(sub_county__in=selected_subcounties)
        if selected_chus:        qs = qs.filter(community_health_unit__in=selected_chus)
        return qs

    def get_sync_qs(chw_batch):
        sync_batch = find_matching_sync_batch(chw_batch)
        if sync_batch is None:
            return None
        qs = CHPSyncRecord.objects.filter(batch=sync_batch).exclude(
            county='').exclude(sub_county='').exclude(community_health_unit='')
        if selected_counties:    qs = qs.filter(county__in=selected_counties)
        if selected_subcounties: qs = qs.filter(sub_county__in=selected_subcounties)
        if selected_chus:        qs = qs.filter(community_health_unit__in=selected_chus)
        return qs

    metrics_prev_month   = compute_scorecard_metrics(get_chw_qs(batch_prev_month),   get_sync_qs(batch_prev_month))   if batch_prev_month   else None
    metrics_prev_week    = compute_scorecard_metrics(get_chw_qs(batch_prev_week),     get_sync_qs(batch_prev_week))    if batch_prev_week    else None
    metrics_current_week = compute_scorecard_metrics(get_chw_qs(batch_current_week),  get_sync_qs(batch_current_week)) if batch_current_week else None

    # Build scorecard rows
    rows = []
    for key, meta in SCORECARD_TARGETS.items():
        target     = meta['target']
        row_type   = meta.get('type', 'simple')

        def make_cell(metrics, key=key, target=target, meta=meta, row_type=row_type):
            if metrics is None:
                return {'value': None, 'display': '—', 'colour': 'grey', 'pct_target': None, 'type': row_type}

            if row_type == 'active_chps':
                val   = metrics.get('active_chps', 0)
                pct   = metrics.get('active_chps_pct', 0)
                total = metrics.get('total_chps', 0)
                if pct >= 90:   colour = 'green'
                elif pct >= 70: colour = 'yellow'
                else:           colour = 'red'
                return {
                    'value': val, 'colour': colour, 'pct_target': round(pct, 1),
                    'pct_colour': colour,  # same threshold for % achieved column
                    'type': row_type,
                    'display': f"{val} ({pct}%)",
                    'detail': f"of {total} total CHPs",
                }

            elif row_type == 'child_health':
                ru5  = metrics.get('total_registered_u5', 0)
                au5  = metrics.get('total_u5_assessed', 0)
                upct = metrics.get('u5_assessment_pct', 0)
                iccm = metrics.get('iccm_assessments', 0)
                pos  = metrics.get('total_positive_diag', 0)
                avg  = metrics.get('avg_positive_diag', 0)
                fc   = metrics.get('fever_cases', 0)
                ft   = metrics.get('fever_tested', 0)
                colour = get_colour(upct, 100)
                return {
                    'value': upct, 'colour': colour, 'pct_target': round(upct, 1), 'type': row_type,
                    'lines': [
                        ('U5 Pop', f"{ru5:,}"),
                        ('Assessed', f"{au5:,} ({upct}%)"),
                        ('iCCM Assessments', f"{iccm:,}"),
                        ('Sick Children (avg)', f"{pos:,} ({avg})"),
                        ('Fever', f"{fc:,} tested {ft:,}"),
                    ]
                }

            elif row_type == 'pnc':
                val  = metrics.get('pnc_ontime_pct', 0)
                num  = metrics.get('pnc_numerator', 0)
                den  = metrics.get('pnc_denominator', 0)
                pct_target = round(val / target * 100, 1) if target else None
                colour = get_colour(val, target)
                return {
                    'value': val, 'colour': colour, 'pct_target': pct_target, 'type': row_type,
                    'display': f"{val}% ({num}/{den})",
                }

            elif row_type == 'iccm_ref':
                val  = metrics.get('iccm_referral_pct')
                comp = metrics.get('iccm_ref_completed', 0)
                tot  = metrics.get('iccm_referrals', 0)
                if val is None:
                    return {'value': None, 'display': '—', 'colour': 'grey', 'pct_target': None, 'type': row_type}
                pct_target = round(val / target * 100, 1) if target else None
                colour = get_colour(val, target)
                return {
                    'value': val, 'colour': colour, 'pct_target': pct_target, 'type': row_type,
                    'display': f"{comp} ({val}%)",
                }

            else:
                val = metrics.get(key)
                if val is None:
                    return {'value': None, 'display': '—', 'colour': 'grey', 'pct_target': None, 'type': row_type}
                unit = meta['unit']
                display = f"{val}{unit}" if unit == '%' else str(val)
                pct_target = round(val / target * 100, 1) if target else None
                colour = get_colour(val, target, meta['higher_is_better'])
                return {'value': val, 'display': display, 'colour': colour, 'pct_target': pct_target, 'type': row_type}

        # Monthly target display
        if row_type == 'child_health':
            target_display = f"100% of {(metrics_current_week or metrics_prev_month or {}).get('total_registered_u5', 0):,} U5s; avg {10} sick children"
        elif row_type == 'active_chps':
            total = (metrics_current_week or metrics_prev_week or metrics_prev_month or {}).get('total_chps', 0)
            target_display = str(total) if total else '—'
        else:
            target_display = f"{target}{meta['unit']}" if target is not None else '—'

        rows.append({
            'key':    key,
            'label':  meta['label'],
            'target': target_display,
            'type':   row_type,
            'prev_month':   make_cell(metrics_prev_month),
            'prev_week':    make_cell(metrics_prev_week),
            'current_week': make_cell(metrics_current_week),
        })

    # Filter options from the most data-rich batch
    filter_batch = batch_current_week or batch_prev_week or batch_prev_month
    filter_opts  = {}
    if filter_batch:
        fqs = CHWRecord.objects.filter(batch=filter_batch)
        filter_opts['counties'] = fqs.values_list('county', flat=True).distinct().order_by('county')
        if selected_counties:
            filter_opts['sub_counties'] = fqs.filter(county__in=selected_counties).values_list('sub_county', flat=True).distinct().order_by('sub_county')
        if selected_subcounties:
            filter_opts['chus'] = fqs.filter(sub_county__in=selected_subcounties).values_list('community_health_unit', flat=True).distinct().order_by('community_health_unit')

    # Inactive CHPs from the latest CHW batch (current_week, else prev_week, else prev_month)
    latest_batch = batch_current_week or batch_prev_week or batch_prev_month
    inactive_chps = []
    if latest_batch:
        inactive_qs = CHWRecord.objects.filter(batch=latest_batch, is_active=False)
        if selected_counties:    inactive_qs = inactive_qs.filter(county__in=selected_counties)
        if selected_subcounties: inactive_qs = inactive_qs.filter(sub_county__in=selected_subcounties)
        if selected_chus:        inactive_qs = inactive_qs.filter(community_health_unit__in=selected_chus)

        # Try to get last sync date from matching sync batch
        sync_batch = find_matching_sync_batch(latest_batch)
        sync_lookup = {}
        if sync_batch:
            for rec in CHPSyncRecord.objects.filter(batch=sync_batch).values('username', 'last_sync_date'):
                if rec['username']:
                    sync_lookup[rec['username']] = rec['last_sync_date']

        for r in inactive_qs.order_by('county', 'sub_county', 'community_health_unit', 'chw_name'):
            last_sync = sync_lookup.get(r.username)
            inactive_chps.append({
                'chw_name':              r.chw_name,
                'county':                r.county,
                'sub_county':            r.sub_county,
                'community_health_unit': r.community_health_unit,
                'chp_area':              r.chp_area,
                'last_sync_date':        str(last_sync) if last_sync else '—',
            })

    return render(request, 'dashboard/scorecard.html', {
        'rows':               rows,
        'all_batches':        all_batches,
        'batch_prev_month':   batch_prev_month,
        'batch_prev_week':    batch_prev_week,
        'batch_current_week': batch_current_week,
        'latest_batch':       latest_batch,
        'override_prev_month':   override_prev_month,
        'override_prev_week':    override_prev_week,
        'override_current_week': override_current_week,
        'filter_opts':           filter_opts,
        'selected_counties':     selected_counties,
        'selected_subcounties':  selected_subcounties,
        'selected_chus':         selected_chus,
        'inactive_chps':         inactive_chps,
        'is_uploader': is_uploader(request.user) if request.user.is_authenticated else False,
    })


@login_required
def download_inactive_chps(request):
    county     = request.GET.get('county', '')
    sub_county = request.GET.get('sub_county', '')
    chu        = request.GET.get('chu', '')
    batch_id   = request.GET.get('batch')

    if batch_id:
        batch = get_object_or_404(UploadBatch, pk=batch_id)
    else:
        batch = UploadBatch.objects.order_by('-year', '-month', '-week_start_date').first()

    if not batch:
        return HttpResponse('No batch found', status=404)

    qs = CHWRecord.objects.filter(batch=batch, is_active=False)
    if county:     qs = qs.filter(county=county)
    if sub_county: qs = qs.filter(sub_county=sub_county)
    if chu:        qs = qs.filter(community_health_unit=chu)

    sync_batch  = find_matching_sync_batch(batch)
    sync_lookup = {}
    if sync_batch:
        for rec in CHPSyncRecord.objects.filter(batch=sync_batch).values('username', 'last_sync_date'):
            if rec['username']:
                sync_lookup[rec['username']] = rec['last_sync_date']

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="inactive_chps_{batch.label}.csv"'
    writer = csv.writer(response)
    writer.writerow(['CHP Name', 'County', 'Sub-County', 'Community Health Unit', 'CHP Area', 'Last Sync Date'])
    for r in qs.order_by('county', 'sub_county', 'community_health_unit', 'chw_name'):
        last_sync = sync_lookup.get(r.username, '—')
        writer.writerow([r.chw_name, r.county, r.sub_county, r.community_health_unit, r.chp_area, last_sync])
    return response