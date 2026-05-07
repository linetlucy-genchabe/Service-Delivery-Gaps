from django.contrib import admin
from .models import UploadBatch, CHWRecord, SupervisionRecord


@admin.register(UploadBatch)
class UploadBatchAdmin(admin.ModelAdmin):
    list_display  = ['label', 'period_type', 'year', 'month', 'week_start_date', 'uploaded_by', 'uploaded_at']
    list_filter   = ['period_type', 'year', 'month']
    search_fields = ['notes']
    readonly_fields = ['uploaded_at']


@admin.register(CHWRecord)
class CHWRecordAdmin(admin.ModelAdmin):
    list_display  = ['chw_name', 'chw_id', 'community_health_unit', 'sub_county', 'county', 'is_active', 'hh_visits', 'supervised', 'batch']
    list_filter   = ['is_active', 'supervised', 'county', 'batch']
    search_fields = ['chw_name', 'chw_id', 'community_health_unit']


@admin.register(SupervisionRecord)
class SupervisionRecordAdmin(admin.ModelAdmin):
    list_display  = ['chv_name', 'community_health_unit', 'sub_county', 'county', 'visit_date', 'assessment_score', 'batch']
    list_filter   = ['county', 'batch']
    search_fields = ['chv_name', 'community_health_unit']
