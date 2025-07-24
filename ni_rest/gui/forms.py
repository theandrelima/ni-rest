from django import forms
from django.core.exceptions import ValidationError

from ni_rest.api.models import NetworkImporterInventorySettings, NetworkImporterNetCreds, BatfishServiceSetting

class ExecuteJobForm(forms.Form):
    # Dry-run checkbox is now FIRST field
    dry_run = forms.BooleanField(
        initial=True,  # Default checked (dry-run/check mode)
        required=False,
        label="Dry-run mode (no changes will be applied)",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="When checked, only show what changes would be made without applying them"
    )
    
    # Site code is SECOND
    site_code = forms.CharField(
        max_length=50, 
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Site code (e.g., NYC01)'}),
        help_text="Unique identifier for the site"
    )
    
    inventory_settings = forms.ModelChoiceField(
        queryset=NetworkImporterInventorySettings.objects.all(),
        empty_label="Select inventory settings",
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Inventory provider configuration"
    )
    
    network_credentials = forms.ModelChoiceField(
        queryset=NetworkImporterNetCreds.objects.all(),
        empty_label="Select network credentials",
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Network device credentials"
    )
    
    batfish_settings = forms.ModelChoiceField(
        queryset=BatfishServiceSetting.objects.all(),
        empty_label="Select Batfish settings (optional)",
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Batfish service configuration (optional)"
    )
    
    # Extra settings field (LAST)
    extra_settings = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Additional settings in JSON format (optional)'
        }),
        help_text="Additional settings in JSON format if needed"
    )
    
    def clean(self):
        cleaned_data = super().clean()
        
        # If at least one inventory setting doesn't exist
        if not NetworkImporterInventorySettings.objects.exists():
            raise ValidationError(
                "No inventory settings available. Please create one in the admin panel."
            )
        
        # If at least one network credential doesn't exist
        if not NetworkImporterNetCreds.objects.exists():
            raise ValidationError(
                "No network credentials available. Please create one in the admin panel."
            )
        
        return cleaned_data