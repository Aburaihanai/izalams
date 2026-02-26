from .models import Message
from .models import VideoPost
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from .models import GalleryImage
from .models import Announcement
from django import forms
from .models import User, Profile, State, LGA, Ward, OrganizationUnit
from django.contrib.auth import get_user_model
from .constants import BANK_CHOICES


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
    # 1. Security & Identity
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Create Secure Password'})
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Repeat Password'})
    )

    # 2. Organizational Choice (Crucial for Leader Routing)
    category = forms.ChoiceField(
        choices=OrganizationUnit.CATEGORY_CHOICES,
        initial='FAG',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    level = forms.ChoiceField(
        choices=OrganizationUnit.LEVEL_CHOICES,
        initial='WARD',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    # 3. Location Hierarchy
    state = forms.ModelChoiceField(
        queryset=State.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    lga = forms.ModelChoiceField(
        queryset=LGA.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    # Ensure Ward is a CharField (Text Input) and also not required
    ward = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter Ward/Branch Name'
        })
    )

    # 4. Profile Specifics
    position = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Youth Leader or Member'})
    )
    profile_picture = forms.ImageField(required=False, widget=forms.FileInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = [
            'username', 'first_name', 'last_name', 'email', 'phone_number',
            'education_level', 'course_of_study', 'is_graduated', 'graduation_year'
        ]
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Choose Username'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number'}),
            'education_level': forms.Select(attrs={'class': 'form-select'}),
            'course_of_study': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. B.Sc Computer Science'}),
            'graduation_year': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'YYYY'}),
            'is_graduated': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Logic to maintain dropdown selections if the form fails validation
        if 'state' in self.data:
            try:
                state_id = int(self.data.get('state'))
                self.fields['lga'].queryset = LGA.objects.filter(state_id=state_id).order_by('name')
            except (ValueError, TypeError): pass

        if 'lga' in self.data:
            try:
                lga_id = int(self.data.get('lga'))
                self.fields['ward'].queryset = Ward.objects.filter(lga_id=lga_id).order_by('name')
            except (ValueError, TypeError): pass

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Passwords do not match!")
        return cleaned_data

class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['subject', 'body']

class GalleryForm(forms.ModelForm):
    class Meta:
        model = GalleryImage
        fields = ['title', 'image', 'order']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter image title'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
        }

class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ['content', 'is_active']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Write your announcement here...'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class UserUpdateForm(forms.ModelForm):
    # Override the bank_code field to be a dropdown
    bank_code = forms.ChoiceField(
        choices=BANK_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'account_number', 'bank_code']

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['profile_picture', 'education_level', 'course_of_study', 'graduation_year']