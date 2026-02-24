import openpyxl
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.utils.translation import gettext as _
import csv
import requests
from axes.utils import reset
from django.contrib.auth.views import LoginView
from django.contrib.auth.views import PasswordResetView
from axes.models import AccessAttempt
from django.contrib.auth.views import PasswordResetConfirmView
from django.db.models import Sum
# Import all your models
from .models import (
    User, Profile, OrganizationUnit,
    VideoPost, PayrollRecord, Announcement, NewsUpdate, GalleryImage
)

# Import all your forms
from .forms import (
    RegistrationForm, ProfileForm, VideoUploadForm,
    MessageForm
)

# --- 1. PUBLIC VIEWS ---

def landing_page(request):
    """The public home page with news, scrolling announcements, and video feed."""
    announcements = Announcement.objects.filter(is_active=True).order_by('-created_at')
    news = NewsUpdate.objects.all()[:3]
    videos = VideoPost.objects.all().order_by('-created_at')[:4]
    gallery = GalleryImage.objects.all()[:6]

    return render(request, 'landing.html', {
        'announcements': announcements,
        'news': news,
        'videos': videos,
        'gallery': gallery
    })

def register(request):
    """Handles dual creation of User and Profile models."""
    if request.method == 'POST':
        user_form = RegistrationForm(request.POST)
        profile_form = ProfileForm(request.POST)

        if user_form.is_valid() and profile_form.is_valid():
            # Save User
            user = user_form.save(commit=False)
            user.set_password(user_form.cleaned_data['password'])
            user.save()

            # Save Profile linked to User
            profile = profile_form.save(commit=False)
            profile.user = user
            profile.is_active = False # Requires admin approval
            profile.save()

            messages.success(request, _("Registration successful! Your branch leader must activate your account before you can login."))
            return redirect('login')
    else:
        user_form = RegistrationForm()
        profile_form = ProfileForm()

    return render(request, 'accounts/register.html', {
        'user_form': user_form,
        'profile_form': profile_form
    })

class CustomLoginView(LoginView):
    template_name = 'login.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Standard IP lookup
        x_fwd = self.request.META.get('HTTP_X_FORWARDED_FOR')
        ip = x_fwd.split(',')[0] if x_fwd else self.request.META.get('REMOTE_ADDR')

        # Use the correct field name found in your console
        attempt = AccessAttempt.objects.filter(ip_address=ip).first()

        # Fix: access 'failures_since_start' instead of 'failures'
        failures = attempt.failures_since_start if attempt else 0

        limit = 5
        context['remaining_attempts'] = max(0, limit - failures)
        context['show_warning'] = failures > 0
        context['lockout_expires'] = attempt.expiration if attempt else None
        return context

class CustomPasswordResetView(PasswordResetView):
    template_name = 'password_reset.html'

    def form_valid(self, form):
        # Pass the request directly without 'request='
        reset(username=User.username)
        return super().form_valid(form)

class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'password_reset_confirm.html'

    def form_valid(self, form):
        # 1. This actually saves the new password to the database
        response = super().form_valid(form)

        # 2. This clears the Axes lockout so the user can log in immediately
        reset(self.request)

        return response

def leader_directory(request):
    """Public directory showing only verified/active leaders."""
    profiles = Profile.objects.filter(is_active=True).select_related('user', 'unit')
    return render(request, 'leader_directory.html', {'profiles': profiles})


# --- 2. MANAGEMENT & DASHBOARD ---

@login_required
def dashboard(request):
    user = request.user

    # 1. Handle Staff Actions (Adding Gallery/Announcements)
    if request.method == 'POST' and user.is_staff:
        if 'add_announcement' in request.POST:
            content = request.POST.get('content')
            if content:
                Announcement.objects.create(content=content)
            return redirect('dashboard')

        if 'add_gallery' in request.POST:
            title = request.POST.get('title')
            image = request.FILES.get('image')
            if image:
                GalleryImage.objects.create(title=title, image=image)
            return redirect('dashboard')

    # 2. Safe Profile Fetching
    # We use .filter().first() so it returns None instead of crashing if no profile exists
    user_profile = Profile.objects.filter(user=user, is_active=True).first()

    # 3. Initialize default data (empty if no profile/unit)
    members = []
    pending = []
    total_spent = 0

    if user_profile and user_profile.unit:
        # Get active members for this unit
        members = Profile.objects.filter(unit=user_profile.unit, is_active=True)
        # Get pending members for this unit
        pending = Profile.objects.filter(unit=user_profile.unit, is_active=False)
        # Calculate total payouts for this unit
        total_spent = PayrollRecord.objects.filter(
            member__profiles__unit=user_profile.unit,
            status='paid'
        ).aggregate(Sum('amount'))['amount__sum'] or 0

    # 4. Global Data (Announcements for the ticker)
    announcements = Announcement.objects.filter(is_active=True).order_by('-created_at')

    context = {
        'leader_profile': user_profile, # Keep name same as your template
        'members': members,
        'pending': pending,
        'total_spent': total_spent,
        'announcements': announcements,
    }
    return render(request, 'dashboard.html', context)

@login_required
def members_list(request):
    """The full list of users with search and category filtering."""
    query = request.GET.get('q')
    category_filter = request.GET.get('category')

    # Capital 'U' User.objects avoids your previous AttributeError
    members = User.objects.all().prefetch_related('profiles__unit')

    if query:
        members = members.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(phone_number__icontains=query) |
            Q(username__icontains=query)
        )

    if category_filter:
        members = members.filter(profiles__unit__category=category_filter)

    return render(request, 'accounts/members_list.html', {
        'members': members.distinct(),
        'query': query
    })

@login_required
def member_detail(request, member_id):
    """Individual profile view."""
    member = get_object_or_404(User, id=member_id)
    profile = member.profiles.first() # Getting the primary profile
    return render(request, 'accounts/member_detail.html', {'member': member, 'profile': profile})

@login_required
def approve_member(request, profile_id):
    """Action view to activate a profile."""
    profile = get_object_or_404(Profile, id=profile_id)
    profile.is_active = True
    profile.save()
    messages.success(request, _(f"Account for {profile.user.get_full_name()} activated."))
    return redirect('dashboard')


# --- 3. PAYROLL & DATA ---

@login_required
def export_members_excel(request):
    """Generates a multilingual Excel sheet of the directory."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "JIBWIS Directory"

    ws.append([_("Username"), _("Full Name"), _("Phone"), _("Bank Code"), _("Account No")])

    for u in User.objects.all():
        ws.append([u.username, u.get_full_name(), u.phone_number, u.bank_code, u.account_number])

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=JIBWIS_Export.xlsx'
    wb.save(response)
    return response

@login_required
def payroll_history(request):
    records = PayrollRecord.objects.all().order_by('-payment_date')
    return render(request, 'payroll_history.html', {'records': records})


# --- 4. COMMUNICATION & CONTENT ---

@login_required
def send_message(request, recipient_id):
    recipient = get_object_or_404(User, id=recipient_id)
    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            msg = form.save(commit=False)
            msg.sender = request.user
            msg.recipient = recipient
            msg.save()
            messages.success(request, _("Official memo sent."))
            return redirect('member_detail', member_id=recipient.id)
    else:
        form = MessageForm()
    return render(request, 'accounts/send_message.html', {'form': form, 'recipient': recipient})

@login_required
def upload_video(request):
    if request.method == 'POST':
        form = VideoUploadForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, _("Video published to feed."))
            return redirect('landing')
    else:
        form = VideoUploadForm()
    return render(request, 'upload_video.html', {'form': form})


# --- 5. ACCOUNT & AUTH STUBS ---

@login_required
def update_username(request):
    if request.method == 'POST':
        new_name = request.POST.get('username')
        if not User.objects.filter(username=new_name).exists():
            request.user.username = new_name
            request.user.save()
            messages.success(request, _("Username updated."))
        else:
            messages.error(request, _("Username already taken."))
    return render(request, 'accounts/update_username.html')

@login_required
def delete_account(request):
    if request.method == 'POST':
        request.user.delete()
        return redirect('landing')
    return render(request, 'accounts/confirm_delete.html')

# Payment Stubs (Integration points)
def initiate_payment(request, member_id):
    return HttpResponse("Redirecting to Gateway...")
def verify_payment(request):
    return JsonResponse({'status': 'pending'})
def bulk_payroll(request):
    return HttpResponse("Processing Bulk Transfers...")
def payment_receipt(request, reference):
    return render(request, 'receipt_pdf.html', {'ref': reference})

@login_required
def export_payroll_csv(request):
    # Create the HttpResponse object with the appropriate CSV header.
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="JIBWIS_Payroll_History.csv"'

    writer = csv.writer(response)
    # Write the header row
    writer.writerow([_('Member'), _('Amount'), _('Reference'), _('Status'), _('Date')])

    # Pull records from your PayrollRecord model
    records = PayrollRecord.objects.all().select_related('member')
    for record in records:
        writer.writerow([
            record.member.get_full_name(),
            record.amount,
            record.reference,
            record.status,
            record.payment_date.strftime("%Y-%m-%d %H:%M")
        ])

    return response

def verify_bank_account(request):
    bank_code = request.GET.get('bank_code')
    account_number = request.GET.get('account_number')

    if not bank_code or not account_number:
        return JsonResponse({'error': 'Missing data'}, status=400)

    url = f"https://api.paystack.co/bank/resolve?account_number={account_number}&bank_code={bank_code}"
    headers = {
        "Authorization": f"Bearer YOUR_PAYSTACK_SECRET_KEY",
        "Content-Type": "application/json",
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()

        if data.get('status'):
            # Paystack returns account_name inside the 'data' object
            return JsonResponse({'account_name': data['data']['account_name']})
        else:
            return JsonResponse({'error': data.get('message')}, status=400)
    except requests.exceptions.RequestException:
        return JsonResponse({'error': 'Connection to Paystack failed'}, status=503)

@login_required
def member_search(request):
    """
    Advanced filtering for members based on User details and
    OrganizationUnit categories/levels.
    """
    query = request.GET.get('q', '')
    category = request.GET.get('category', '')
    level = request.GET.get('level', '')

    # Start with all users who have an active profile
    results = User.objects.all().prefetch_related('profiles__unit')

    # 1. Text Search (Name, Phone, Email)
    if query:
        results = results.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(phone_number__icontains=query) |
            Q(email__icontains=query)
        )

    # 2. Filter by Category (ADMIN, ULAMA, FAG)
    if category:
        results = results.filter(profiles__unit__category=category)

    # 3. Filter by Organizational Level (NATIONAL, STATE, etc.)
    if level:
        results = results.filter(profiles__unit__level=level)

    # Remove duplicates if a user has multiple profiles
    results = results.distinct()

    context = {
        'members': results,
        'query': query,
        'category': category,
        'level': level,
        'categories': OrganizationUnit.CATEGORY_CHOICES,
        'levels': OrganizationUnit.LEVEL_CHOICES,
    }

    return render(request, 'accounts/search.html', context)
