from django import forms
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
                'placeholder': 'Shigar da sunan ka'
            }),
            'donor_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'shigar da imel ɗinka'
            }),
            'donor_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Shigar da lambar wayarka'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control amount-input',
                'min': '100',
                'step': '0.01',
                'placeholder': '100.00'
            }),
            'purpose': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Zakka'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Shigar da kowane bayani (na zaɓi)'
            }),
            'payment_method': forms.RadioSelect(attrs={
                'class': 'form-check-input'
            })
        }
        labels = {
            'donor_name': 'Sunanka',
            'donor_email': 'Imel',
            'donor_phone': 'Lambar Wayarka',
            'amount': 'Yawan Kudi (₦)',
            'purpose': 'Dalili',
            'notes': 'Bayani (Na zaɓi)',
            'payment_method': 'Hanyar Biya'
        }

class CardPaymentForm(forms.Form):
    card_number = forms.CharField(
        max_length=19,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '1234 5678 9012 3456'
        })
    )
    expiry_date = forms.CharField(
        max_length=5,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'MM/YY'
        })
    )
    cvv = forms.CharField(
        max_length=3,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '123'
        })
    )
    card_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Sunan da ke kan kati'
        })
    )