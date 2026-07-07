from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import UploadBatch, PERIOD_TYPE_CHOICES, MONTH_CHOICES
import datetime


CURRENT_YEAR = datetime.date.today().year
YEAR_CHOICES = [(y, y) for y in range(CURRENT_YEAR - 1, CURRENT_YEAR + 2)]


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Username'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Password'})
    )


class UploadBatchForm(forms.ModelForm):
    year = forms.ChoiceField(choices=YEAR_CHOICES, initial=CURRENT_YEAR)
    month = forms.ChoiceField(choices=MONTH_CHOICES)
    period_type = forms.ChoiceField(
        choices=PERIOD_TYPE_CHOICES,
        label='Period Type',
        widget=forms.RadioSelect(attrs={'class': 'radio-input'}),
    )
    week_start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        label='Week Start Date',
        help_text='First day of the reporting period (e.g. 2026-05-01)',
    )
    week_end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        label='Week End Date (optional)',
        help_text='Last day of the reporting period (e.g. 2026-05-15). Leave blank for a standard week label.',
    )
    chw_file = forms.FileField(
        label='CHW Detail File (.xlsx)',
        widget=forms.FileInput(attrs={'class': 'file-input', 'accept': '.xlsx'}),
    )
    supervision_file = forms.FileField(
        label='Supervision File (.xlsx)',
        widget=forms.FileInput(attrs={'class': 'file-input', 'accept': '.xlsx'}),
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Optional notes about this upload'}),
    )

    class Meta:
        model = UploadBatch
        fields = ['period_type', 'year', 'month', 'week_start_date', 'week_end_date', 'chw_file', 'supervision_file', 'notes']

    def clean(self):
        cleaned = super().clean()
        period_type = cleaned.get('period_type')
        week_start  = cleaned.get('week_start_date')
        if period_type == 'weekly' and not week_start:
            self.add_error('week_start_date', 'Week start date is required for weekly uploads.')
        return cleaned


class KPIReportForm(forms.ModelForm):
    class Meta:
        from .models import KPIReport
        model  = KPIReport
        fields = ['file', 'report_month', 'report_year', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 2}),
        }