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
        'registered_children_u5', 'num_u5_assessed', 'positive_diagnoses_u5'
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
    """Compare two sync batches to identify consistent non-syncers etc."""
    batches    = SyncUploadBatch.objects.all().order_by('-year', '-month', '-week_start_date')
    batch_a_id = request.GET.get('batch_a', '')
    batch_b_id = request.GET.get('batch_b', '')
    county     = request.GET.get('county', '')
    sub_county = request.GET.get('sub_county', '')
    chu        = request.GET.get('chu', '')

    comparison  = None
    filter_opts = {}

    if batch_a_id and batch_b_id and batch_a_id != batch_b_id:
        batch_a = get_object_or_404(SyncUploadBatch, pk=batch_a_id)
        batch_b = get_object_or_404(SyncUploadBatch, pk=batch_b_id)

        def base_qs(batch):
            qs = CHPSyncRecord.objects.filter(batch=batch).exclude(
                county='').exclude(sub_county='').exclude(community_health_unit='')
            if county:     qs = qs.filter(county=county)
            if sub_county: qs = qs.filter(sub_county=sub_county)
            if chu:        qs = qs.filter(community_health_unit=chu)
            return qs

        qs_a = base_qs(batch_a)
        qs_b = base_qs(batch_b)

        # Build lookup dicts keyed by username
        def to_dict(qs):
            return {
                r['username']: r for r in qs.values(
                    'username', 'chp_name', 'county', 'sub_county',
                    'community_health_unit', 'days_synced', 'reports_synced', 'last_sync_date'
                )
            }

        dict_a = to_dict(qs_a)
        dict_b = to_dict(qs_b)

        all_usernames = set(dict_a.keys()) | set(dict_b.keys())

        synced_both       = []  # synced in both
        synced_a_only     = []  # synced in A but not B
        synced_b_only     = []  # synced in B but not A
        never_synced_both = []  # never synced in either

        for username in sorted(all_usernames):
            a = dict_a.get(username)
            b = dict_b.get(username)
            in_a_synced = a and a['days_synced'] >= 1
            in_b_synced = b and b['days_synced'] >= 1
            in_a = bool(a)
            in_b = bool(b)

            row = {
                'username':               username,
                'chp_name':               (a or b)['chp_name'],
                'county':                 (a or b)['county'],
                'sub_county':             (a or b)['sub_county'],
                'community_health_unit':  (a or b)['community_health_unit'],
                'days_synced_a':          a['days_synced'] if a else '—',
                'days_synced_b':          b['days_synced'] if b else '—',
                'last_sync_a':            str(a['last_sync_date']) if a and a['last_sync_date'] else 'Never',
                'last_sync_b':            str(b['last_sync_date']) if b and b['last_sync_date'] else 'Never',
                'in_a': in_a, 'in_b': in_b,
            }

            if in_a_synced and in_b_synced:
                synced_both.append(row)
            elif in_a_synced and not in_b_synced:
                synced_a_only.append(row)
            elif in_b_synced and not in_a_synced:
                synced_b_only.append(row)
            else:
                never_synced_both.append(row)

        # Filter options from batch_a for cascading filters
        filter_qs = CHPSyncRecord.objects.filter(batch=batch_a).exclude(
            county='').exclude(sub_county='').exclude(community_health_unit='')
        filter_opts['counties']    = filter_qs.values_list('county', flat=True).distinct().order_by('county')
        if county:
            filter_opts['sub_counties'] = filter_qs.filter(county=county).values_list('sub_county', flat=True).distinct().order_by('sub_county')
        if sub_county:
            filter_opts['chus'] = filter_qs.filter(county=county, sub_county=sub_county).values_list('community_health_unit', flat=True).distinct().order_by('community_health_unit')

        comparison = {
            'batch_a': batch_a,
            'batch_b': batch_b,
            'synced_both':       synced_both,
            'synced_a_only':     synced_a_only,
            'synced_b_only':     synced_b_only,
            'never_synced_both': never_synced_both,
            'total': len(all_usernames),
            'count_both':   len(synced_both),
            'count_a_only': len(synced_a_only),
            'count_b_only': len(synced_b_only),
            'count_never':  len(never_synced_both),
        }

    return render(request, 'dashboard/sync_compare.html', {
        'batches':     batches,
        'batch_a_id':  batch_a_id,
        'batch_b_id':  batch_b_id,
        'comparison':  comparison,
        'filter_opts': filter_opts,
        'selected_county':    county,
        'selected_subcounty': sub_county,
        'selected_chu':       chu,
        'is_uploader': is_uploader(request.user) if request.user.is_authenticated else False,
    })


@require_GET
def api_compare_download(request):
    """CSV download for any comparison category."""
    batch_a_id = request.GET.get('batch_a')
    batch_b_id = request.GET.get('batch_b')
    category   = request.GET.get('category', 'never_synced_both')
    county     = request.GET.get('county', '')
    sub_county = request.GET.get('sub_county', '')
    chu        = request.GET.get('chu', '')

    batch_a = get_object_or_404(SyncUploadBatch, pk=batch_a_id)
    batch_b = get_object_or_404(SyncUploadBatch, pk=batch_b_id)

    def base_qs(batch):
        qs = CHPSyncRecord.objects.filter(batch=batch).exclude(
            county='').exclude(sub_county='').exclude(community_health_unit='')
        if county:     qs = qs.filter(county=county)
        if sub_county: qs = qs.filter(sub_county=sub_county)
        if chu:        qs = qs.filter(community_health_unit=chu)
        return qs

    dict_a = {r['username']: r for r in base_qs(batch_a).values(
        'username', 'chp_name', 'county', 'sub_county',
        'community_health_unit', 'days_synced', 'last_sync_date')}
    dict_b = {r['username']: r for r in base_qs(batch_b).values(
        'username', 'chp_name', 'county', 'sub_county',
        'community_health_unit', 'days_synced', 'last_sync_date')}

    all_usernames = set(dict_a.keys()) | set(dict_b.keys())
    rows = []
    for username in sorted(all_usernames):
        a = dict_a.get(username)
        b = dict_b.get(username)
        in_a_synced = a and a['days_synced'] >= 1
        in_b_synced = b and b['days_synced'] >= 1
        row = {
            'username': username,
            'chp_name': (a or b)['chp_name'],
            'county': (a or b)['county'],
            'sub_county': (a or b)['sub_county'],
            'community_health_unit': (a or b)['community_health_unit'],
            'days_a': a['days_synced'] if a else '—',
            'days_b': b['days_synced'] if b else '—',
            'last_a': str(a['last_sync_date']) if a and a['last_sync_date'] else 'Never',
            'last_b': str(b['last_sync_date']) if b and b['last_sync_date'] else 'Never',
        }
        if category == 'synced_both'       and in_a_synced and in_b_synced:         rows.append(row)
        elif category == 'synced_a_only'   and in_a_synced and not in_b_synced:     rows.append(row)
        elif category == 'synced_b_only'   and in_b_synced and not in_a_synced:     rows.append(row)
        elif category == 'never_synced_both' and not in_a_synced and not in_b_synced: rows.append(row)

    labels = {
        'synced_both':       'Synced in Both Periods',
        'synced_a_only':     f'Synced in {batch_a.label} Only',
        'synced_b_only':     f'Synced in {batch_b.label} Only',
        'never_synced_both': 'Never Synced in Either Period',
    }

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="sync_comparison_{category}.csv"'
    writer = csv.writer(response)
    writer.writerow(['Category', 'County', 'Sub-County', 'Community Health Unit',
                     'CHP Name', 'Username',
                     f'Days Synced ({batch_a.label})', f'Last Sync ({batch_a.label})',
                     f'Days Synced ({batch_b.label})', f'Last Sync ({batch_b.label})'])
    for r in rows:
        writer.writerow([labels.get(category, category), r['county'], r['sub_county'],
                         r['community_health_unit'], r['chp_name'], r['username'],
                         r['days_a'], r['last_a'], r['days_b'], r['last_b']])
    return response


# ===========================================================================
# WEEKLY PERFORMANCE SCORECARD
# ===========================================================================

# Hardcoded targets (universal across all counties/sub-counties/CHUs)
SCORECARD_TARGETS = {
    'active_chps_pct':     {'target': 100, 'unit': '%',  'label': 'Active CHPs',               'higher_is_better': True},
    'hh_coverage_pct':     {'target': 85,  'unit': '%',  'label': 'HH Coverage',                'higher_is_better': True},
    'avg_positive_diag':   {'target': 10,  'unit': '',   'label': 'Avg Positive Diagnoses/CHP', 'higher_is_better': True},
    'pnc_ontime_pct':      {'target': 85,  'unit': '%',  'label': 'On Time PNC',                'higher_is_better': True},
    'preg_registered_chp': {'target': 1,   'unit': '',   'label': 'Preg Registered/CHP',        'higher_is_better': True},
    'sync_rate_pct':       {'target': 80,  'unit': '%',  'label': '% CHPs Syncing Weekly',      'higher_is_better': True},
    'supervision_pct':     {'target': 65,  'unit': '%',  'label': '% CHPs Supervised',          'higher_is_better': True},
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
    # Use supervision_visits > 0 from CHW Detail (more reliable than supervised boolean
    # which can be 100% in weekly extracts). Falls back to supervised boolean if no visits data.
    supervised_via_visits = active_qs.filter(supervision_visits__gt=0).count()
    supervised_via_bool   = active_qs.filter(supervised=True).count()
    # Prefer supervision_visits count if it gives a more realistic result
    # If supervised_via_visits == total_active it likely means field not populated — use bool
    supervised = supervised_via_visits if supervised_via_visits < total_active else supervised_via_bool
    sup_pct = round(supervised / total_active * 100, 1) if total_active else 0

    # 7. Sync rate — from sync queryset if provided
    sync_pct = None
    if sync_qs is not None:
        total_sync = sync_qs.count()
        synced     = sync_qs.filter(days_synced__gte=1).count()
        sync_pct   = round(synced / total_sync * 100, 1) if total_sync else 0

    return {
        'active_chps':        total_active,
        'total_chps':         total_all,
        'active_chps_pct':    active_pct,
        'hh_coverage_pct':    hh_coverage,
        'avg_positive_diag':  avg_pos,
        'pnc_ontime_pct':     pnc_pct,
        'preg_registered_chp': preg_per_chp,
        'supervision_pct':    sup_pct,
        'sync_rate_pct':      sync_pct,
    }


def get_colour(value, target, higher_is_better=True):
    """Return green/yellow/red based on % of target achieved."""
    if value is None or target == 0:
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
    county     = request.GET.get('county', '')
    sub_county = request.GET.get('sub_county', '')
    chu        = request.GET.get('chu', '')

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
        if county:     qs = qs.filter(county=county)
        if sub_county: qs = qs.filter(sub_county=sub_county)
        if chu:        qs = qs.filter(community_health_unit=chu)
        return qs

    def get_sync_qs(chw_batch):
        sync_batch = find_matching_sync_batch(chw_batch)
        if sync_batch is None:
            return None
        qs = CHPSyncRecord.objects.filter(batch=sync_batch).exclude(
            county='').exclude(sub_county='').exclude(community_health_unit='')
        if county:     qs = qs.filter(county=county)
        if sub_county: qs = qs.filter(sub_county=sub_county)
        if chu:        qs = qs.filter(community_health_unit=chu)
        return qs

    metrics_prev_month   = compute_scorecard_metrics(get_chw_qs(batch_prev_month),   get_sync_qs(batch_prev_month))   if batch_prev_month   else None
    metrics_prev_week    = compute_scorecard_metrics(get_chw_qs(batch_prev_week),     get_sync_qs(batch_prev_week))    if batch_prev_week    else None
    metrics_current_week = compute_scorecard_metrics(get_chw_qs(batch_current_week),  get_sync_qs(batch_current_week)) if batch_current_week else None

    # Build scorecard rows
    rows = []
    for key, meta in SCORECARD_TARGETS.items():
        target = meta['target']

        def cell(metrics, key=key, target=target, hib=meta['higher_is_better']):
            if metrics is None:
                return {'value': None, 'display': '—', 'colour': 'grey', 'pct_target': None}
            val = metrics.get(key)
            if val is None:
                return {'value': None, 'display': '—', 'colour': 'grey', 'pct_target': None}
            unit = meta['unit']
            display = f"{val}{unit}" if unit == '%' else str(val)
            pct_target = round(val / target * 100, 1) if target else None
            colour = get_colour(val, target, hib)
            return {'value': val, 'display': display, 'colour': colour, 'pct_target': pct_target}

        rows.append({
            'key':    key,
            'label':  meta['label'],
            'target': f"{target}{meta['unit']}",
            'prev_month':   cell(metrics_prev_month),
            'prev_week':    cell(metrics_prev_week),
            'current_week': cell(metrics_current_week),
        })

    # Filter options from the most data-rich batch
    filter_batch = batch_current_week or batch_prev_week or batch_prev_month
    filter_opts  = {}
    if filter_batch:
        fqs = CHWRecord.objects.filter(batch=filter_batch)
        filter_opts['counties'] = fqs.values_list('county', flat=True).distinct().order_by('county')
        if county:
            filter_opts['sub_counties'] = fqs.filter(county=county).values_list('sub_county', flat=True).distinct().order_by('sub_county')
        if sub_county:
            filter_opts['chus'] = fqs.filter(county=county, sub_county=sub_county).values_list('community_health_unit', flat=True).distinct().order_by('community_health_unit')

    return render(request, 'dashboard/scorecard.html', {
        'rows':               rows,
        'all_batches':        all_batches,
        'batch_prev_month':   batch_prev_month,
        'batch_prev_week':    batch_prev_week,
        'batch_current_week': batch_current_week,
        'override_prev_month':   override_prev_month,
        'override_prev_week':    override_prev_week,
        'override_current_week': override_current_week,
        'filter_opts':        filter_opts,
        'selected_county':    county,
        'selected_subcounty': sub_county,
        'selected_chu':       chu,
        'is_uploader':        is_uploader(request.user) if request.user.is_authenticated else False,
    })