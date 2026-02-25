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
from .utils import send_jibwis_sms
from django.conf import settings
from django.db.models import Count
from django.db import transaction
from .models import (
    User, Profile, Message, OrganizationUnit,
    VideoPost, PayrollRecord, Announcement, NewsUpdate, GalleryImage, DisciplinaryReport,
    Disbursement
)

# Import all your forms
from .forms import (
    RegistrationForm, ProfileForm, VideoUploadForm,
    MessageForm, UserUpdateForm, ProfileUpdateForm
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
    if request.method == 'POST':
        user_form = RegistrationForm(request.POST)
        profile_form = ProfileForm(request.POST)

        if user_form.is_valid() and profile_form.is_valid():
            try:
                with transaction.atomic():
                    # 1. Save the User account
                    user = user_form.save(commit=False)
                    user.set_password(user_form.cleaned_data['password'])
                    user.save()

                    # 2. Save the Profile and link it to the new User
                    profile = profile_form.save(commit=False)
                    profile.user = user
                    profile.is_active = False  # Keep isolated until Leader approves
                    profile.save()

                messages.success(request, "Registration successful! Your Unit Leader must approve your account.")
                return redirect('login')
            except Exception:
                messages.error(request, "An error occurred. Please try again.")
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
    # Fetch profile to identify the leader's unit and category
    user_profile = Profile.objects.filter(user=user).first()

    # Global trending content
    trending_videos = VideoPost.objects.annotate(
        like_count=Count('likes')
    ).order_by('-like_count')[:3]

    # 1. STAFF ACTIONS (POST) - Restricted to Leaders
    if request.method == 'POST' and user.is_staff:
        # Leaders can post announcements visible only to their unit or global
        if 'add_announcement' in request.POST:
            content = request.POST.get('content')
            if content:
                # Associate announcement with leader's unit for isolation
                Announcement.objects.create(content=content, unit=user_profile.unit)
            return redirect('dashboard')

        if 'add_gallery' in request.POST:
            title = request.POST.get('title')
            image = request.FILES.get('image')
            if image:
                GalleryImage.objects.create(title=title, image=image)
            return redirect('dashboard')

    # 2. INITIALIZE UNIT-SPECIFIC VARIABLES
    members = []
    pending = []
    unit_leaders = []
    total_spent = 0

    # Ensure profile exists before filtering unit data
    if user_profile and user_profile.unit:

        # 3. LOGIC FOR REGULAR MEMBERS (Non-Staff)
        if not user.is_staff:
            # Show leaders in their specific unit for reporting/contact
            unit_leaders = Profile.objects.filter(unit=user_profile.unit, user__is_staff=True)

        # 4. LOGIC FOR LEADERS (Staff)
        else:
            # Isolation: Leaders only see members within their own unit
            members = Profile.objects.filter(unit=user_profile.unit, is_active=True).exclude(user=user)

            # Pending approvals: Restricted to the leader's branch
            pending = Profile.objects.filter(unit=user_profile.unit, is_active=False)

            # Financial Oversight: Unit-specific payroll total
            total_spent = PayrollRecord.objects.filter(
                member__profiles__unit=user_profile.unit,
                status='success'
            ).aggregate(Sum('amount'))['amount__sum'] or 0

    # 5. MESSAGING & NOTIFICATIONS
    # Exclude soft-deleted messages as previously fixed
    messages_received = Message.objects.filter(
        recipient=user,
        recipient_deleted=False
    ).order_by('-timestamp')

    # Announcements: Only show those relevant to the user's unit or global ones
    announcements = Announcement.objects.filter(
        is_active=True,
        unit=user_profile.unit
    ).order_by('-created_at')

    context = {
        'leader_profile': user_profile,
        'members': members,
        'pending': pending,
        'unit_leaders': unit_leaders,
        'total_spent': total_spent,
        'announcements': announcements,
        'messages_received': messages_received,
        'trending_videos': trending_videos,
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

# accounts/views.py
def member_detail(request, pk):
    leader_profile = request.user.profiles.first()
    # Fetch the Profile, which links to the User
    member_profile = get_object_or_404(Profile, user_id=pk, unit=leader_profile.unit)

    return render(request, 'accounts/member_detail.html', {
        'member': member_profile
    })

@login_required
def approve_member(request, profile_id):
    # Only staff/leaders can perform this action
    if not request.user.is_staff:
        messages.error(request, "Access denied. Only leaders can approve members.")
        return redirect('dashboard')

    # Fetch the pending profile
    # Safety check: Ensure the member is in the same unit as the leader
    leader_profile = request.user.profiles.first()
    member_profile = get_object_or_404(
        Profile,
        id=profile_id,
        unit=leader_profile.unit,
        is_active=False
    )

    if request.method == 'POST':
        member_profile.is_active = True
        member_profile.save()

        # Optional: Send a notification message to the new member
        Message.objects.create(
            sender=request.user,
            recipient=member_profile.user,
            subject="Account Activated",
            body="Welcome! Your branch leader has approved your registration."
        )

        messages.success(request, f"Member {member_profile.user.username} has been approved.")

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
    leader_profile = request.user.profiles.first()

    # Base Query: Get all disbursements made by this leader or within their scope
    # This assumes you have a 'Disbursement' model or similar to track payments
    history = Disbursement.objects.filter(
        authorized_by=request.user
    ).order_by('-timestamp')

    context = {
        'history': history,
        'leader_profile': leader_profile,
    }
    return render(request, 'payroll_history.html', context)
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


def verify_payment(request):
    return JsonResponse({'status': 'pending'})

@login_required
def bulk_payroll_page(request):
    leader_profile = request.user.profiles.first()
    if not leader_profile or not leader_profile.unit:
        messages.error(request, "Access Denied.")
        return redirect('dashboard')

    leader_unit = leader_profile.unit
    category = leader_unit.category
    level = leader_unit.level  # Assumes your model has 'level'
    query = request.GET.get('q', '')

    # Base Query: Start with everyone in the same category
    personnel = User.objects.filter(profiles__unit__category=category).distinct().exclude(id=request.user.id)

    # Apply Level Restrictions
    if level == 'STATE':
        # State leaders only see personnel within their specific state
        personnel = personnel.filter(profiles__unit__state=leader_unit.state)
    elif level == 'LGA':
        # LGA leaders only see personnel within their specific LGA
        personnel = personnel.filter(profiles__unit__lga=leader_unit.lga)
    elif level == 'WARD':
        # Ward leaders only see personnel in their specific ward
        personnel = personnel.filter(profiles__unit=leader_unit)
    # If level is 'NATIONAL', no extra filter is applied (they see everyone)

    # Apply Search Filter
    if query:
        personnel = personnel.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(profiles__unit__name__icontains=query)
        )

    context = {
        'members': personnel.order_by('profiles__unit__level', 'profiles__unit__name'),
        'leader_profile': leader_profile,
        'category_name': category,
        'paystack_balance': get_paystack_balance(),
        'search_query': query,
    }
    return render(request, 'bulk_payroll.html', context)


def initiate_paystack_transfer(recipient_user, amount):
    # Paystack uses Kobo (100 Kobo = 1 Naira)
    amount_in_kobo = int(float(amount) * 100)

    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }

    # Step 1: Create Transfer Recipient
    recipient_data = {
        "type": "nuban",
        "name": recipient_user.get_full_name(),
        "account_number": recipient_user.account_number,
        "bank_code": recipient_user.bank_code, # e.g., '058' for GTB
        "currency": "NGN"
    }

    rcp_res = requests.post("https://api.paystack.co/transferrecipient", json=recipient_data, headers=headers)

    if rcp_res.status_code == 201:
        recipient_code = rcp_res.json()['data']['recipient_code']

        # Step 2: Initiate Transfer
        transfer_data = {
            "source": "balance",
            "amount": amount_in_kobo,
            "recipient": recipient_code,
            "reason": "JIBWIS Unit Payroll"
        }

        trn_res = requests.post("https://api.paystack.co/transfer", json=transfer_data, headers=headers)
        return trn_res.json()

    return None

@login_required
def process_payroll(request):
    if request.method == 'POST':
        selected_ids = request.POST.getlist('selected_members')
        processed_count = 0

        for p_id in selected_ids:
            amount = request.POST.get(f'amount_{p_id}')
            recipient = User.objects.get(id=p_id)

            # CALL PAYSTACK
            response = initiate_paystack_transfer(recipient, amount)

            if response and response.get('status'):
                # Save to Ledger only if Paystack accepted it
                Disbursement.objects.create(
                    authorized_by=request.user,
                    recipient=recipient,
                    amount=amount,
                    status='PROCESSING', # Paystack transfers are often queued
                    transaction_reference=response['data'].get('reference')
                )
                processed_count += 1

        messages.success(request, f"Successfully initiated {processed_count} real-time transfers.")
        return redirect('payroll_history')

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


@login_required
def message_view(request):
    # Enforce isolation: Only leaders (staff) can send/reply to messages
    if not request.user.is_staff:
        messages.error(request, "Access denied. Only leaders can send official replies.")
        return redirect('dashboard')

    if request.method == 'POST':
        recipient_id = request.POST.get('recipient')
        subject = request.POST.get('subject')
        body = request.POST.get('body')

        # Ensure subject starts with "Re:" if it's a reply
        if subject and not subject.startswith("Re:"):
            subject = f"Re: {subject}"

        recipient = get_object_or_404(User, id=recipient_id)

        # Create the message
        Message.objects.create(
            sender=request.user,
            recipient=recipient,
            subject=subject,
            body=body
        )

        messages.success(request, "Reply successfully sent!")
        return redirect('dashboard')

@login_required
def mark_as_read(request, message_id):
    # Ensure the message belongs to the person trying to read it
    message = get_object_or_404(Message, id=message_id, recipient=request.user)
    message.is_read = True
    message.save()
    return redirect('dashboard')

@login_required
def submit_report(request):
    if request.method == 'POST':
        leader_id = request.POST.get('subject_leader')
        complaint = request.POST.get('complaint')
        evidence = request.FILES.get('evidence')

        subject_leader = get_object_or_404(User, id=leader_id)

        # Create the report
        DisciplinaryReport.objects.create(
            reporter=request.user,
            subject_leader=subject_leader,
            complaint=complaint,
            evidence=evidence
        )

        messages.success(request, "Your report has been submitted to the National Disciplinary Committee.")
        return redirect('dashboard')

    return redirect('dashboard')

@login_required
def disciplinary_admin(request):
    # Security Check: Only National level staff can see this
    profile = request.user.profiles.first()
    if not request.user.is_staff or profile.unit.level != 'NAT':
        messages.error(request, "Access Denied: High-level Clearance Required.")
        return redirect('dashboard')

    reports = DisciplinaryReport.objects.all().order_by('-created_at')

    return render(request, 'disciplinary_list.html', {'reports': reports})

@login_required
def edit_profile(request):
    profile = request.user.profiles.first()
    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(request.POST, instance=profile)
        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, "Profile updated successfully!")
            return redirect('dashboard')

        if u_form.is_valid():
            user = u_form.save(commit=False)
            # If bank details changed, verify them
            real_name = verify_bank_account(user.account_number, user.bank_code)
            if real_name:
                user.account_name = real_name # Auto-fill the verified name
            user.save()
    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=profile)

    if request.method == 'POST':
        account_no = request.POST.get('account_number')
        bank_cd = request.POST.get('bank_code')

        # Verify before saving
        verified_name = verify_bank_account(account_no, bank_cd)

        if verified_name:
            # Save the profile and store the verified name for extra safety
            profile = request.user.profiles.first()
            request.user.account_number = account_no
            request.user.bank_code = bank_cd
            request.user.verified_bank_name = verified_name
            request.user.save()
            messages.success(request, f"Account Verified: {verified_name}")
        else:
            messages.error(request, "Could not verify bank details. Please check the number and bank.")

    return render(request, 'accounts/edit_profile.html', {
        'u_form': u_form,
        'p_form': p_form
    })
@login_required
def bulk_message_send(request):
    if request.method == 'POST' and request.user.is_staff:
        member_ids = request.POST.getlist('selected_members')
        subject = request.POST.get('subject')
        body = request.POST.get('body')
        category = request.POST.get('category')  # New: Get category from form

        # Get the leader's profile safely
        leader_profile = request.user.profiles.first()
        if not leader_profile:
            messages.error(request, "Adarí kò ní àkọsílẹ̀ (Leader profile not found).")
            return redirect('members_list')

        leader_unit = leader_profile.unit

        # Build the QuerySet
        # We use category__iexact for a case-insensitive match
        # 1. Start with the IDs selected in the form
        query_filter = {'id__in': member_ids}

        # 2. Add Unit restriction (unless the leader is National HQ)
        if leader_unit.name != "National HQ":
            query_filter['profiles__unit'] = leader_unit

        # 3. ONLY filter by category if a category was actually selected
        if category and category.strip():
            query_filter['profiles__category__iexact'] = category

        recipients = User.objects.filter(**query_filter).distinct()

        if not recipients.exists():
            messages.warning(request, f"Notification sent to 0 members. Check if members match Unit: {leader_unit} and Category: {category}")
            return redirect('members_list')

        for recipient in recipients:
            # 1. Internal Message
            Message.objects.create(
                sender=request.user,
                recipient=recipient,
                subject=subject,
                body=body
            )

            # 2. SMS Alert (Using getattr to avoid errors if field is missing)
            phone = getattr(recipient, 'phone_number', None)
            if phone:
                # Yoruba/English mixed SMS prefix
                sms_prefix = f"JIBWIS {leader_unit}:"
                sms_text = f"{sms_prefix} {subject}. {body[:100]}..."
                send_jibwis_sms(phone, sms_text)

        messages.success(request, f"The message has been sent to the member. {recipients.count()} (Sent to {recipients.count()} members).")

    return redirect('members_list')

@login_required
def toggle_member_status(request, member_id):
    if not request.user.is_staff:
        messages.error(request, "Access denied.")
        return redirect('dashboard')

    # 1. Get the Leader's unit
    leader_profile = request.user.profiles.first()
    if not leader_profile or not leader_profile.unit:
        messages.error(request, "You are not assigned to a unit.")
        return redirect('dashboard')

    # 2. Find the target member's profile
    # We use filter().first() instead of get_object_or_404 to avoid the 404 crash
    target_profile = Profile.objects.filter(user_id=member_id, unit=leader_profile.unit).first()

    if not target_profile:
        messages.error(request, "Member profile not found or belongs to another unit.")
        return redirect('members_list')

    # 3. Handle the Deactivation Reason
    reason = request.GET.get('reason', 'No reason provided')

    # Toggle the status
    target_profile.is_active = not target_profile.is_active
    target_profile.save()

    # Log the action (optional: you could save 'reason' to a Discipline model here)
    status_text = "Activated" if target_profile.is_active else f"Deactivated (Reason: {reason})"
    messages.success(request, f"Member {target_profile.user.get_full_name()} is now {status_text}.")

    return redirect('members_list')

@login_required
def delete_member_permanent(request, user_id):
    # Only Leaders/Staff allowed
    if not request.user.is_staff:
        messages.error(request, "Permission denied.")
        return redirect('dashboard')

    # Get the Leader's unit
    leader_profile = request.user.profiles.first()
    if not leader_profile:
        messages.error(request, "You do not have a Leader Profile assigned.")
        return redirect('dashboard')

    # FIX: Use a more specific filter to find the user in the leader's unit
    # This prevents the 404 if the user exists but is in the wrong unit
    member_to_delete = User.objects.filter(
        id=user_id,
        profiles__unit=leader_profile.unit
    ).first()

    if not member_to_delete:
        messages.error(request, f"User ID {user_id} not found in your unit ({leader_profile.unit}).")
        return redirect('members_list')

    if request.method == 'POST':
        username = member_to_delete.username
        member_to_delete.delete()
        messages.success(request, f"User {username} deleted permanently.")
        return redirect('members_list')

    return redirect('members_list')

def verify_bank_account(account_no, bank_code):
    url = f"https://api.paystack.co/bank/resolve?account_number={account_no}&bank_code={bank_code}"
    headers = {"Authorization": "Bearer YOUR_SECRET_KEY"}

    response = requests.get(url, headers=headers)
    data = response.json()

    if data.get('status'):
        return data['data']['account_name'] # Returns the real name from the bank
    return None

@login_required
def verify_account_ajax(request):
    """
    Handles internal AJAX requests to verify bank accounts via Paystack.
    """
    account_number = request.GET.get('acc')
    bank_code = request.GET.get('bank')

    if not account_number or not bank_code:
        return JsonResponse({'success': False, 'message': 'Missing data'})

    # Using the verify_bank_account function we discussed earlier
    verified_name = verify_bank_account(account_number, bank_code)

    if verified_name:
        return JsonResponse({
            'success': True,
            'account_name': verified_name
        })
    else:
        return JsonResponse({
            'success': False,
            'message': 'Account could not be resolved'
        })

def get_paystack_balance():
    """Fetches the current account balance from Paystack."""
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
    }
    try:
        response = requests.get("https://api.paystack.co/balance", headers=headers)
        data = response.json()
        if data.get('status'):
            # The balance is an array of currencies; we find NGN
            for balance in data['data']:
                if balance['currency'] == 'NGN':
                    return balance['balance'] / 100
    except Exception:
        pass
    return 0.00


def toggle_video_like(request, video_id):
    video = get_object_or_404(VideoPost, id=video_id)

    # Check if user is logged in
    if request.user.is_authenticated:
        user_id = str(request.user.id)
        if request.user in video.likes.all():
            video.likes.remove(request.user)
            liked = False
        else:
            video.likes.add(request.user)
            liked = True
    else:
        # GUEST LOGIC: Use Session ID
        if not request.session.session_key:
            request.session.create()

        session_key = request.session.session_key
        # We store guest likes in a list inside the session
        guest_likes = request.session.get('guest_liked_videos', [])

        if video_id in guest_likes:
            guest_likes.remove(video_id)
            # Technically we can't 'remove' from ManyToMany for guests
            # unless we create a GuestLike model, so we just track count
            # via a separate field or just track UI state.
            liked = False
        else:
            guest_likes.append(video_id)
            liked = True

        request.session['guest_liked_videos'] = guest_likes
        # For simplicity in this setup, guests only toggle the UI icon
        # but don't increase the DB ManyToMany count unless you add a field.
        # To make guest likes permanent, use:
        # video.views_count += 1 (or a new field video.anonymous_likes)

    return JsonResponse({
        'liked': liked,
        'count': video.total_likes()
    })

def video_detail(request, video_id):
    video = get_object_or_404(VideoPost, id=video_id)
    # Increment view count
    video.views_count += 1
    video.save()
    return render(request, 'video_detail.html', {'video': video})

@login_required
def delete_message(request, msg_id):
    if request.method == 'POST':
        # Get the message specifically for this recipient
        message = get_object_or_404(Message, id=msg_id, recipient=request.user)

        # Set the flag to True
        message.recipient_deleted = True
        message.save()  # This sends the change to the database

        messages.success(request, "The message has been deleted (Message deleted).")

    # Redirect back to where they came from
    return redirect(request.META.get('HTTP_REFERER', 'inbox'))

@login_required
def inbox(request):
    # Corrected: Use order_by with a minus sign for descending order (newest first)
    messages_received = Message.objects.filter(
        recipient=request.user,
        recipient_deleted=False
    ).order_by('-timestamp')

    return render(request, 'accounts/inbox.html', {
        'messages_received': messages_received
    })