from django import forms
from django.utils import timezone
from .models import Service


class QuoteForm(forms.Form):
    name = forms.CharField(max_length=200)
    phone = forms.CharField(max_length=40, required=False)
    email = forms.EmailField(max_length=200, required=False)
    service = forms.ModelChoiceField(queryset=Service.objects.all(), to_field_name="slug")
    city = forms.CharField(max_length=200, label="City / barangay")
    property_type = forms.CharField(max_length=200)
    sqm = forms.DecimalField(min_value=0.1, max_value=100000, max_digits=9, decimal_places=1)
    preferred_date = forms.DateField()
    description = forms.CharField(max_length=3000)
    rooms = forms.IntegerField(min_value=0, max_value=1000, required=False)
    special_requests = forms.CharField(max_length=3000, required=False)
    privacy_consent = forms.BooleanField(required=True)

    def clean(self):
        data = super().clean()
        if not data.get("phone") and not data.get("email"):
            raise forms.ValidationError("Provide a phone number or email address so we can reply.")
        return data

    def clean_phone(self):
        value = self.cleaned_data["phone"]
        digits = ''.join(c for c in value if c.isdigit())
        if value and not 7 <= len(digits) <= 15:
            raise forms.ValidationError("Enter a valid phone number.")
        return value

    def clean_preferred_date(self):
        value = self.cleaned_data["preferred_date"]
        if value < timezone.localdate():
            raise forms.ValidationError("Choose today or a future date. Availability will be confirmed separately.")
        return value
