from django.db import models
from django.contrib.auth.models import User


PERIOD_TYPE_CHOICES = [
    ('monthly', 'Monthly'),
    ('weekly',  'Weekly'),
]

MONTH_CHOICES = [
    (1,  'January'),   (2,  'February'), (3,  'March'),
    (4,  'April'),     (5,  'May'),      (6,  'June'),
    (7,  'July'),      (8,  'August'),   (9,  'September'),
    (10, 'October'),   (11, 'November'), (12, 'December'),
]


class UploadBatch(models.Model):
    """
    One batch = one paired upload of CHW Detail + Supervision files
    for a specific reporting period (month or week).
    """
    uploaded_by   = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    uploaded_at   = models.DateTimeField(auto_now_add=True)

    # Period metadata (manually selected by uploader)
    period_type   = models.CharField(max_length=10, choices=PERIOD_TYPE_CHOICES)
    year          = models.PositiveSmallIntegerField()
    month         = models.PositiveSmallIntegerField(choices=MONTH_CHOICES)
    # For weekly uploads: the anchor date shown to users e.g. "9 Apr 2026"
    week_start_date = models.DateField(null=True, blank=True)

    # Raw files kept for audit / re-processing
    chw_file        = models.FileField(upload_to='uploads/chw/')
    supervision_file = models.FileField(upload_to='uploads/supervision/')

    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-year', '-month', '-week_start_date']
        verbose_name = 'Upload Batch'
        verbose_name_plural = 'Upload Batches'

    def __str__(self):
        if self.period_type == 'weekly' and self.week_start_date:
            return f"Week of {self.week_start_date.strftime('%d %b %Y').lstrip('0')} ({self.get_month_display()} {self.year})"
        return f"{self.get_month_display()} {self.year} – Monthly"

    @property
    def label(self):
        return str(self)


class CHWRecord(models.Model):
    """
    One row from the CHW Detail file, linked to an UploadBatch.
    Column names are normalised from the Excel headers.
    """
    batch = models.ForeignKey(UploadBatch, on_delete=models.CASCADE, related_name='chw_records')

    # Geography
    county                  = models.CharField(max_length=100)
    sub_county              = models.CharField(max_length=100)
    community_health_unit   = models.CharField(max_length=200)
    chp_area                = models.CharField(max_length=200, blank=True)

    # CHP identity
    chw_name    = models.CharField(max_length=200)
    chw_id      = models.CharField(max_length=100, blank=True)
    username    = models.CharField(max_length=100, blank=True)
    is_active   = models.BooleanField(default=True)

    # Household
    registered_hhs      = models.IntegerField(default=0)
    hh_visits           = models.IntegerField(default=0)
    new_hhs_registered  = models.IntegerField(default=0)

    # Pregnancy & ANC
    pregnancies_registered  = models.IntegerField(default=0)
    active_pregnancies      = models.IntegerField(default=0)
    pregnancies_visited     = models.IntegerField(default=0)
    pregnancy_visits        = models.IntegerField(default=0)
    anc_total_deliveries    = models.IntegerField(default=0)
    deliveries_4plus_anc    = models.IntegerField(default=0)
    deliveries_with_anc_data = models.IntegerField(default=0)
    first_trimester_registrations = models.IntegerField(default=0)
    iron_folate_count       = models.IntegerField(default=0)

    # Delivery & PNC
    total_deliveries        = models.IntegerField(default=0)
    facility_deliveries     = models.IntegerField(default=0)
    pnc_48hr_ontime         = models.IntegerField(default=0)
    pnc_3_7d_ontime         = models.IntegerField(default=0)

    # iCCM (Under-5 case management)
    registered_children_u5  = models.IntegerField(default=0)
    registered_children_u2  = models.IntegerField(default=0)
    num_u5_assessed         = models.IntegerField(default=0)
    iccm_assessments        = models.IntegerField(default=0)
    positive_diagnoses_u5   = models.IntegerField(default=0)
    treated_visits_u5       = models.IntegerField(default=0)
    malaria_diagnosed       = models.IntegerField(default=0)
    pneumonia_diagnosed     = models.IntegerField(default=0)
    diarrhea_diagnosed      = models.IntegerField(default=0)
    malaria_managed         = models.IntegerField(default=0)
    pneumonia_managed       = models.IntegerField(default=0)
    diarrhea_managed        = models.IntegerField(default=0)
    danger_sign_referred    = models.IntegerField(default=0)
    fever_cases             = models.IntegerField(default=0)
    fever_tested_rdt        = models.IntegerField(default=0)
    iccm_referrals_total    = models.IntegerField(default=0)
    iccm_referral_followup  = models.IntegerField(default=0)
    iccm_referrals_u2mo     = models.IntegerField(default=0)
    iccm_completed_referrals_u2mo = models.IntegerField(default=0)
    u1_positive_diagnoses   = models.IntegerField(default=0)
    u1_treated_visits       = models.IntegerField(default=0)
    u1_sick_assessments     = models.IntegerField(default=0)

    # Immunisation
    iz_assessments          = models.IntegerField(default=0)
    iz_fully_immunized      = models.IntegerField(default=0)
    iz_children_9_23mo      = models.IntegerField(default=0)
    iz_defaulters           = models.IntegerField(default=0)
    iz_defaulters_followed  = models.IntegerField(default=0)
    iz_defaulters_completed = models.IntegerField(default=0)

    # Family Planning
    fp_assessments          = models.IntegerField(default=0)
    fp_new_users            = models.IntegerField(default=0)
    fp_unique_new_users     = models.IntegerField(default=0)
    fp_current_users        = models.IntegerField(default=0)
    fp_wra_assessed         = models.IntegerField(default=0)
    fp_cyp                  = models.IntegerField(default=0)
    fp_non_users_assessed   = models.IntegerField(default=0)
    fp_needing_refill       = models.IntegerField(default=0)
    fp_refilled             = models.IntegerField(default=0)
    fp_referred             = models.IntegerField(default=0)
    fp_referral_followup    = models.IntegerField(default=0)
    fp_current_users_18_49  = models.IntegerField(default=0)
    fp_wra_assessed_18_49   = models.IntegerField(default=0)

    # Nutrition
    nutrition_assessments       = models.IntegerField(default=0)
    muac_screened               = models.IntegerField(default=0)
    mam_sam_total               = models.IntegerField(default=0)
    mam_sam_referred            = models.IntegerField(default=0)
    mam_sam_referral_completed  = models.IntegerField(default=0)
    exclusive_bf                = models.IntegerField(default=0)
    u6mo_bf_assessed            = models.IntegerField(default=0)
    complementary_feeding       = models.IntegerField(default=0)
    assessed_6_9mo              = models.IntegerField(default=0)
    vitamin_a_covered           = models.IntegerField(default=0)
    assessed_6_59mo_vita        = models.IntegerField(default=0)

    # Supervision
    days_synced         = models.IntegerField(default=0)
    supervised          = models.BooleanField(default=False)
    supervision_visits  = models.IntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=['batch', 'county']),
            models.Index(fields=['batch', 'county', 'sub_county']),
            models.Index(fields=['batch', 'county', 'sub_county', 'community_health_unit']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.chw_name} – {self.community_health_unit} [{self.batch}]"


class SupervisionRecord(models.Model):
    """
    One row from the Supervision file, linked to an UploadBatch.
    """
    batch = models.ForeignKey(UploadBatch, on_delete=models.CASCADE, related_name='supervision_records')

    # Geography
    county                  = models.CharField(max_length=100)
    sub_county              = models.CharField(max_length=100)
    community_health_unit   = models.CharField(max_length=200)

    # Visit details
    visit_date              = models.DateField()
    chv_name                = models.CharField(max_length=200)
    chv_uuid                = models.CharField(max_length=200, blank=True)
    is_available            = models.BooleanField(default=True)
    visit_sections          = models.TextField(blank=True)

    # Assessment
    has_essential_medicines = models.BooleanField(null=True, blank=True)
    medicines_lacking       = models.TextField(blank=True, default="")
    assessment_score        = models.FloatField(null=True, blank=True)
    assessment_denominator  = models.IntegerField(default=0)
    has_all_tools           = models.BooleanField(null=True, blank=True)
    has_ppe                 = models.BooleanField(null=True, blank=True)

    # Supervisor info
    supervisor_area         = models.CharField(max_length=200, blank=True)
    supervisor_phone        = models.CharField(max_length=50, blank=True)

    # Qualitative
    next_steps              = models.TextField(blank=True)
    overall_observations    = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['batch', 'county']),
            models.Index(fields=['batch', 'county', 'sub_county']),
            models.Index(fields=['batch', 'county', 'sub_county', 'community_health_unit']),
            models.Index(fields=['visit_date']),
        ]

    def __str__(self):
        return f"{self.chv_name} supervised {self.visit_date} [{self.batch}]"


class SyncUploadBatch(models.Model):
    """
    One batch = one sync report file upload for a specific period.
    Completely separate from the CHW/Supervision UploadBatch.
    """
    uploaded_by     = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    uploaded_at     = models.DateTimeField(auto_now_add=True)
    period_type     = models.CharField(max_length=10, choices=PERIOD_TYPE_CHOICES)
    year            = models.PositiveSmallIntegerField()
    month           = models.PositiveSmallIntegerField(choices=MONTH_CHOICES)
    week_start_date = models.DateField(null=True, blank=True)
    sync_file       = models.FileField(upload_to='uploads/sync/')
    notes           = models.TextField(blank=True)

    class Meta:
        ordering = ['-year', '-month', '-week_start_date']
        verbose_name = 'Sync Upload Batch'
        verbose_name_plural = 'Sync Upload Batches'

    def __str__(self):
        if self.period_type == 'weekly' and self.week_start_date:
            return f"Sync – Week of {self.week_start_date.strftime('%d %b %Y').lstrip('0')} ({self.get_month_display()} {self.year})"
        return f"Sync – {self.get_month_display()} {self.year} – Monthly"

    @property
    def label(self):
        return str(self)


class CHPSyncRecord(models.Model):
    """
    One row from the Sync Report file, linked to a SyncUploadBatch.
    """
    batch                 = models.ForeignKey(SyncUploadBatch, on_delete=models.CASCADE, related_name='sync_records')
    county                = models.CharField(max_length=100)
    sub_county            = models.CharField(max_length=100)
    community_health_unit = models.CharField(max_length=200)
    chp_name              = models.CharField(max_length=200)
    username              = models.CharField(max_length=100, blank=True)
    days_synced           = models.IntegerField(default=0)
    reports_synced        = models.IntegerField(default=0)
    last_sync_date        = models.DateField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['batch', 'county'],                                          name='sync_batch_county_idx'),
            models.Index(fields=['batch', 'county', 'sub_county'],                            name='sync_batch_sc_idx'),
            models.Index(fields=['batch', 'county', 'sub_county', 'community_health_unit'],   name='sync_batch_chu_idx'),
        ]

    def __str__(self):
        return f"{self.chp_name} – {self.community_health_unit} [{self.batch}]"