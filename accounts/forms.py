from django import forms
from .models import User, Profile, OrganizationUnit
from .models import Message
from .models import VideoPost
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

class ApprovedOnlyLoginForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        # Check if any of the user's profiles are active
        if not user.profiles.filter(is_active=True).exists():
            raise ValidationError(
                "Your account is pending approval. Please wait for your superior to activate your profile.",
                code='inactive',
            )
            
class VideoUploadForm(forms.ModelForm):
    class Meta:
        model = VideoPost
        fields = ['title', 'video_file']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Friday Khutbah Summary'}),
            'video_file': forms.FileInput(attrs={'class': 'form-control', 'accept': 'video/mp4,video/x-m4v,video/*'})
        }

class RegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Create a secure password'}))

    class Meta:
        model = User
        fields = ['username', 'email', 'phone_number', 'bank_code', 'account_number', 'account_name', 'password']
        widgets = {
            'bank_code': forms.Select(attrs={'class': 'form-select'}),
            'password': forms.PasswordInput(attrs={'class': 'form-control'}),
        }

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['unit', 'position']
        labels = {
            'unit': 'Assigned Unit (Branch/Level)',
            'position': 'Your Official Title'
        }
        
class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['subject', 'body']