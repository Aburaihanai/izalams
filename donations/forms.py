from django import forms
from django.utils.translation import gettext_lazy as _
from .models import Donation

class DonationForm(forms.ModelForm):
    class Meta:
        model = Donation
        fields = [
            'donor_name', 
            'donor_email', 
            'donor_phone',
            'amount', 
            'purpose', 
            'notes',
            'payment_method'
        ]
        widgets = {
            'donor_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Enter your full name')
            }),
            'donor_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': _('Enter your email address')
            }),
            'donor_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Enter your phone number')
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control amount-input',
                'min': '100',
                'step': '0.01',
                'placeholder': '100.00'
            }),
            'purpose': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('e.g., Zakat')
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Enter any additional notes (optional)')
            }),
            'payment_method': forms.RadioSelect(attrs={
                'class': 'form-check-input'
            })
        }
        labels = {
            'donor_name': _('Full Name'),
            'donor_email': _('Email'),
            'donor_phone': _('Phone Number'),
            'amount': _('Amount (₦)'),
            'purpose': _('Purpose'),
            'notes': _('Notes (Optional)'),
            'payment_method': _('Payment Method')
        }

class CardPaymentForm(forms.Form):
    card_number = forms.CharField(
        label=_('Card Number'),
        max_length=19,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '1234 5678 9012 3456'
        })
    )
    expiry_date = forms.CharField(
        label=_('Expiry Date'),
        max_length=5,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'MM/YY'
        })
    )
    cvv = forms.CharField(
        label=_('CVV'),
        max_length=3,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '123'
        })
    )
    card_name = forms.CharField(
        label=_('Cardholder Name'),
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Name as it appears on card')
        })
    )