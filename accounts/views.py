import openpyxl
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.utils.translation import gettext as _
import csv
import requests
from axes.utils import reset
from django.contrib.auth.views import LoginView
from django.contrib.auth.views import PasswordResetView
from axes.models import AccessAttempt
from django.contrib.auth.views import PasswordResetConfirmView
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.db import models
from django.db.models import Sum, Count, Q
from django.urls import reverse_lazy
from django.contrib.auth import get_user_model
from .forms import UserUpdateForm, ProfileUpdateForm
from .utils import verify_bank_account

User = get_user_model()

from .models import (
    User, Profile, Message, OrganizationUnit,
    VideoPost, PayrollRecord, Announcement, GalleryImage, DisciplinaryReport,
    Disbursement, LGA, Ward, State
)

from .forms import (
    RegistrationForm, VideoUploadForm, MessageForm
)

# --- 1. PUBLIC VIEWS ---

def landing_page(request):
    """The public home page with news, scrolling announcements, and video feed."""
    announcements = Announcement.objects.filter(is_active=True).order_by('-created_at')
    videos = VideoPost.objects.all().order_by('-created_at')[:4]
    gallery = GalleryImage.objects.all()[:6]

    return render(request, 'landing.html', {
        'announcements': announcements,
        'videos': videos,
        'gallery': gallery
    })

@transaction.atomic
def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])

            lvl = form.cleaned_data['level']
            cat = form.cleaned_data['category']
            pos = form.cleaned_data.get('position', '').strip()

            # 1. Auto-Approval Logic
            # More flexible staff logic
            is_chairman = 'chairman' in pos.lower()

            if lvl == 'NATIONAL' and is_chairman:
                user.is_active = True
                user.is_staff = True
            elif lvl == 'STATE' and is_chairman:
                user.is_active = False
                user.is_staff = True
            elif lvl == 'LG' and is_chairman:
                user.is_active = False
                user.is_staff = True
            elif lvl == 'WARD' and is_chairman:
                user.is_active = False
                user.is_staff = True
            else:
                user.is_active = False
                user.is_staff = False

            user.save()

            # 2. The Funnel Logic
            unit_filter = {'level': lvl, 'category': cat}

            if lvl == 'STATE':
                unit_filter['state'] = form.cleaned_data['state']
            elif lvl == 'LG':
                unit_filter['state'] = form.cleaned_data['state']
                unit_filter['lga'] = form.cleaned_data['lga']
            elif lvl == 'WARD':
                unit_filter['state'] = form.cleaned_data['state']
                unit_filter['lga'] = form.cleaned_data['lga']
                unit_filter['ward_name'] = form.cleaned_data.get('ward', '').strip()

            # 3. SAFER Get or Create (Fixes MultipleObjectsReturned)
            # We filter first to see if ANY match exists
            target_unit = OrganizationUnit.objects.filter(**unit_filter).first()

            if not target_unit:
                # If nothing exists, we create it
                default_name = f"{lvl} {cat} Unit"
                if lvl == 'WARD':
                    default_name = f"{unit_filter.get('ward_name')} Branch ({cat})"
                elif lvl == 'NATIONAL':
                    default_name = f"JIBWIS National HQ ({cat})"

                target_unit = OrganizationUnit.objects.create(
                    **unit_filter,
                    name=default_name
                )

            # 4. Create the Profile
            Profile.objects.create(
                user=user,
                unit=target_unit,
                position=pos,
                profile_picture=form.cleaned_data.get('profile_picture'),
                is_active=user.is_active
            )

            status_msg = "Approved and Active." if user.is_active else "Pending Leader Approval."
            messages.success(request, f"Registration Successful! Account {status_msg}")
            return redirect('login')
        else:
            # If form is invalid, errors will be sent to the template
            messages.error(request, "Please correct the errors below.")
    else:
        form = RegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})

class CustomLoginView(LoginView):
    template_name = 'login.html'

    def form_valid(self, form):
        """
        Executed when credentials are correct.
        We check if the Profile is active before allowing entry.
        """
        user = form.get_user()
        profile = user.profiles.first()

        if profile and not profile.is_active:
            messages.error(
                self.request,
                "Your account is pending leader approval. Please contact your Unit Secretary."
            )
            return self.form_invalid(form)

        # Log successful login metadata (IP and Timestamp)
        x_fwd = self.request.META.get('HTTP_X_FORWARDED_FOR')
        ip = x_fwd.split(',')[0] if x_fwd else self.request.META.get('REMOTE_ADDR')

        # Optional: You could save this to a 'LoginHistory' model here
        print(f"Login Success: {user.username} from IP {ip} at {timezone.now()}")

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Standard IP lookup for security warnings
        x_fwd = self.request.META.get('HTTP_X_FORWARDED_FOR')
        ip = x_fwd.split(',')[0] if x_fwd else self.request.META.get('REMOTE_ADDR')

        # Axes Security Logic
        attempt = AccessAttempt.objects.filter(ip_address=ip).first()
        failures = attempt.failures_since_start if attempt else 0

        limit = 5
        context['remaining_attempts'] = max(0, limit - failures)
        context['show_warning'] = failures > 0
        context['lockout_expires'] = attempt.expiration if attempt else None

        return context

    def get_success_url(self):
        # Everyone goes to the dashboard now
        return reverse_lazy('dashboard')

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

@login_required
def leader_directory(request):
    """Public directory showing only verified/active leaders with filtering."""

    # 1. Base QuerySet with valid select_related fields
    # Using unit__lga and unit__state as identified in your previous error
    queryset = Profile.objects.filter(is_active=True).select_related(
        'user',
        'unit__lga',
        'unit__state'
    )

    # 2. Filter by Category (Fixed: Looking through the Unit relationship)
    category = request.GET.get('category')
    if category:
        queryset = queryset.filter(unit__category=category)

    # 3. Filter by State
    state_id = request.GET.get('state')
    if state_id:
        queryset = queryset.filter(unit__state_id=state_id)

    # 4. Filter by LGA
    lga_id = request.GET.get('lga')
    if lga_id:
        queryset = queryset.filter(unit__lga_id=lga_id)

    # 5. Search by Name or Phone (Great for finding specific leaders)
    search_query = request.GET.get('q')
    if search_query:
        queryset = queryset.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(user__phone_number__icontains=search_query)
        )

    # 6. Member Exemption check for context
    # This allows the template to hide contact buttons for non-staff members
    is_leader = request.user.is_staff

    context = {
        'profiles': queryset.order_by('user__first_name'),
        'states': State.objects.all(),
        'categories': OrganizationUnit.CATEGORY_CHOICES,
        'is_leader': is_leader,
    }
    return render(request, 'leader_directory.html', context)

# --- 2. MANAGEMENT & DASHBOARD ---
@login_required
def dashboard(request):
    user = request.user
    # 1. Safety Check: Ensure the user has a profile
    user_profile = Profile.objects.filter(user=user).first()

    # If no profile exists (e.g., a new Superuser), redirect to a profile creation or show error
    if not user_profile:
        messages.warning(request, "Your account does not have an assigned Organizational Unit. Please contact the National Admin.")
        return redirect('profile_create') # Or wherever you handle profile setups

    # 2. Redirect inactive profiles
    if not user_profile.is_active:
        return render(request, 'pending_approval.html')

    # Global trending content
    trending_videos = VideoPost.objects.annotate(
        like_count=Count('likes')
    ).order_by('-like_count')[:3]

    # Handle POST Actions
    if request.method == 'POST' and user.is_staff:
        if 'add_announcement' in request.POST:
            content = request.POST.get('content')
            if content:
                # Use the new unit isolation
                Announcement.objects.create(content=content, unit=user_profile.unit)
            return redirect('dashboard')

    # 3. Initialize Variables
    members = []
    pending = []
    unit_leaders = []
    total_spent = 0

    # 4. Hierarchical Data Isolation
    # Only pull data belonging to the Leader's specific Unit (State, LGA, or Ward)
    if user.is_staff:
        # Members in the same unit
        members = Profile.objects.filter(unit=user_profile.unit, is_active=True).exclude(user=user)
        # Pending members awaiting THIS leader's approval
        pending = Profile.objects.filter(unit=user_profile.unit, is_active=False)
        # Financial sum for this specific unit
        total_spent = PayrollRecord.objects.filter(
            member__profiles__unit=user_profile.unit,
            status='success'
        ).aggregate(Sum('amount'))['amount__sum'] or 0
    else:
        # Regular members see who their leaders are
        unit_leaders = Profile.objects.filter(unit=user_profile.unit, user__is_staff=True)

    # 5. Announcements (Unit-specific + National)
    # Filter by user_profile.unit OR global announcements (where unit is NULL)
    announcements = Announcement.objects.filter(
        models.Q(unit=user_profile.unit) | models.Q(unit__isnull=True),
        is_active=True
    ).order_by('-created_at')

    context = {
        'leader_profile': user_profile,
        'members': members,
        'pending': pending,
        'unit_leaders': unit_leaders,
        'total_spent': total_spent,
        'announcements': announcements,
        'messages_received': Message.objects.filter(recipient=user, recipient_deleted=False).order_by('-timestamp'),
        'trending_videos': trending_videos,
    }

    return render(request, 'dashboard.html', context)

@login_required
def members_list(request):
    """The filtered list of users based on the leader's jurisdiction."""
    query = request.GET.get('q')
    category_filter = request.GET.get('category')

    # 1. Get Leader's Information
    leader_profile = getattr(request.user, 'profile', None) or getattr(request.user, 'profiles', None)
    if hasattr(leader_profile, 'first'): leader_profile = leader_profile.first()

    # 2. Base Queryset (Optimized with select_related for unit data)
    # We use 'profile' or 'profiles' based on your model's related_name
    members = User.objects.all().prefetch_related('profiles__unit', 'profiles__unit__state')

    # 3. Apply Hierarchy Filter (Jurisdiction)
    if not request.user.is_superuser:
        if not leader_profile or not leader_profile.unit:
            # If a user has no unit, they see nothing for security
            members = User.objects.none()
        else:
            lvl = leader_profile.unit.level

            if lvl == 'STATE':
                # State Leaders see everyone in their specific State
                members = members.filter(profiles__unit__state=leader_profile.unit.state)

            elif lvl == 'LG':
                # LG Leaders see everyone in their specific LGA
                members = members.filter(profiles__unit__lga=leader_profile.unit.lga)

            elif lvl == 'WARD':
                # Ward Leaders only see their own Branch
                members = members.filter(profiles__unit=leader_profile.unit)

            # Note: NATIONAL level and Superusers continue to see User.objects.all()

    # 4. Apply Search (Name, Username, or Phone)
    if query:
        members = members.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(username__icontains=query) |
            Q(profile__phone_number__icontains=query) # Assuming phone is in Profile
        )

    # 5. Apply Category Filter (First Aid, Ulama, etc.)
    if category_filter:
        members = members.filter(profiles__unit__category=category_filter)

    return render(request, 'accounts/members_list.html', {
        'members': members.distinct().order_by('username'),
        'query': query,
        'leader_profile': leader_profile # Passed so template knows the leader's unit name
    })

def member_detail(request, member_id):
    # 1. Get the profile of the person currently logged in (the viewer)
    # We use .profile (singular) assuming a OneToOneField
    viewer_profile = getattr(request.user, 'profile', None)

    # 2. Fetch the specific member being viewed
    # This is the "member" whose ID is in the URL (e.g., 38)
    member = get_object_or_404(Profile, user__id=member_id)

    return render(request, 'accounts/member_detail.html', {
        'member': member,
        'viewer': viewer_profile
    })

@login_required
def approve_member(request, profile_id):
    # 1. Authority Check
    if not request.user.is_staff:
        messages.error(request, "Access denied. Only leaders can approve members.")
        return redirect('dashboard')

    # 2. Identify the Leader
    leader_profile = getattr(request.user, 'profile', None) or getattr(request.user, 'profiles', None)
    if hasattr(leader_profile, 'first'):
        leader_profile = leader_profile.first()

    if not leader_profile or not leader_profile.unit:
        messages.error(request, "You are not assigned to a unit.")
        return redirect('dashboard')

    # 3. Fetch the Member Profile
    member_profile = get_object_or_404(Profile, id=profile_id)
    member_user = member_profile.user
    member_unit = member_profile.unit

    # 4. HIERARCHY JURISDICTION CHECK
    leader_lvl = leader_profile.unit.level
    can_approve = False

    # Check for unit existence to avoid AttributeErrors
    if not member_unit:
        messages.error(request, "This member has not been assigned to a unit yet.")
        return redirect('members_list')

    if leader_lvl == 'NATIONAL':
        can_approve = True
    elif leader_lvl == 'STATE':
        if member_unit.state == leader_profile.unit.state:
            can_approve = True
    elif leader_lvl == 'LG':
        if member_unit.lga == leader_profile.unit.lga:
            can_approve = True
    # --- ADDED WARD LEVEL LOGIC ---
    elif leader_lvl == 'WARD':
        # Ward Chairmen can only approve members in their exact same Ward
        if member_unit == leader_profile.unit:
            can_approve = True

    if not can_approve:
        messages.error(request, f"Jurisdiction Error: As a {leader_lvl} leader, you cannot manage this member.")
        return redirect('members_list')

    # 5. Process Approval
    if request.method == 'POST':
        member_profile.is_active = True
        member_user.is_active = True

        member_profile.save()
        member_user.save()

        # Send an official JIBWIS notification
        try:
            Message.objects.create(
                sender=request.user,
                recipient=member_user,
                subject="Account Activated",
                body=f"Assalamu Alaikum. Your registration has been approved by the {leader_lvl} office of {leader_profile.unit.name}."
            )
        except Exception:
            pass

        messages.success(request, f"Member {member_user.get_full_name() or member_user.username} has been approved.")

    return redirect('members_list')

# --- 3. PAYROLL & DATA ---

@login_required
def export_members_excel(request):
    # 1. Get the Leader's Profile using the plural 'profiles'
    leader_profile = request.user.profiles.first()

    if not leader_profile or not leader_profile.unit:
        return HttpResponse("Unauthorized jurisdiction.", status=403)

    # 2. Setup Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"{leader_profile.unit.name} Directory"

    # 3. Header Row
    ws.append(['Username', 'Full Name', 'Email', 'Position', 'Level', 'Status'])

    # 4. Filter members based on jurisdiction
    lvl = leader_profile.unit.level

    # Using the local User model we just fetched via get_user_model()
    members = User.objects.all().prefetch_related('profiles__unit')

    if lvl == 'STATE':
        members = members.filter(profiles__unit__state=leader_profile.unit.state)
    elif lvl == 'LG':
        members = members.filter(profiles__unit__lga=leader_profile.unit.lga)

    # 5. Populate Data
    for m in members.distinct():
        p = m.profiles.first()
        ws.append([
            m.username,
            m.get_full_name(),
            m.email,
            p.position if p else "N/A",
            p.unit.level if p and p.unit else "N/A",
            "Active" if m.is_active else "Suspended"
        ])

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename=JIBWIS_Directory.xlsx'
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

    # 1. Jurisdiction Security Check
    leader_profile = request.user.profiles.first()
    recipient_profile = recipient.profiles.first()

    # Ensure leader has a profile and can only message those they oversee
    if not leader_profile or not leader_profile.unit:
        messages.error(request, _("You must be assigned to a unit to send official memos."))
        return redirect('dashboard')

    # Optional: Logic to restrict messaging to jurisdiction
    if not request.user.is_superuser:
        can_message = False
        lvl = leader_profile.unit.level
        if lvl == 'NATIONAL':
            can_message = True
        elif lvl == 'STATE' and recipient_profile:
            if recipient_profile.unit.state == leader_profile.unit.state:
                can_message = True
        elif lvl == 'LG' and recipient_profile:
            if recipient_profile.unit.lga == leader_profile.unit.lga:
                can_message = True

        if not can_message:
            messages.error(request, _("Jurisdiction Error: You can only message members within your region."))
            return redirect('members_list')

    # 2. Handle Message Submission
    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            msg = form.save(commit=False)
            msg.sender = request.user
            msg.recipient = recipient
            msg.save()

            messages.success(request, _("Official memo sent successfully."))
            # Match the URL name you are using for member details
            return redirect('member_detail', member_id=recipient.id)
    else:
        form = MessageForm()

    return render(request, 'accounts/send_message.html', {
        'form': form,
        'recipient': recipient,
        'recipient_profile': recipient_profile
    })
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
        # Added request.FILES for the profile image upload
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)

        if u_form.is_valid() and p_form.is_valid():
            user = u_form.save(commit=False)

            # 1. Bank Verification Logic
            account_no = request.POST.get('account_number')
            bank_cd = request.POST.get('bank_code')

            # Only verify if the account number has changed or is being set
            if account_no and bank_cd:
                verified_name = verify_bank_account(account_no, bank_cd)

                if verified_name:
                    user.account_name = verified_name
                    user.account_number = account_no
                    user.bank_code = bank_cd
                    messages.success(request, f"Bank Account Verified: {verified_name}")
                else:
                    messages.error(request, "Bank verification failed. Please check your details.")
                    return render(request, 'accounts/edit_profile.html', {
                        'u_form': u_form,
                        'p_form': p_form
                    })

            # 2. Final Save
            user.save()
            p_form.save()
            messages.success(request, "Profile updated successfully!")
            return redirect('dashboard')
    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=profile)

    return render(request, 'accounts/edit_profile.html', {
        'u_form': u_form,
        'p_form': p_form
    })

@login_required
def bulk_message_send(request):
    # 1. Handle the POST request (Sending the message)
    if request.method == 'POST':
        recipient_id = request.POST.get('selected_members')
        category = request.POST.get('category')
        subject = request.POST.get('subject')
        body = request.POST.get('body')

        base_recipient = get_object_or_404(User, id=recipient_id)
        base_profile = base_recipient.profiles.first()

        recipients = []
        if not category:
            recipients = [base_recipient]
        else:
            # Broadcast logic
            matching_profiles = Profile.objects.filter(
                unit=base_profile.unit,
                category=category,
                is_active=True
            ).select_related('user')
            recipients = [p.user for p in matching_profiles]

        if recipients:
            message_objs = [
                Message(sender=request.user, recipient=r, subject=subject, body=body)
                for r in recipients
            ]
            Message.objects.bulk_create(message_objs)
            messages.success(request, f"Memo sent successfully to {len(recipients)} member(s).")

        return redirect('member_detail', member_id=recipient_id)

    # 2. Handle the GET request (Displaying the form for Reply)
    # This prevents the 'UnboundLocalError'
    recipient_id = request.GET.get('recipient')
    subject = request.GET.get('subject', '')

    if not recipient_id:
        messages.error(request, "No recipient specified.")
        return redirect('members_list')

    recipient = get_object_or_404(User, id=recipient_id)

    return render(request, 'accounts/send_message.html', {
        'recipient': recipient,
        'initial_subject': subject
    })


@login_required
def toggle_member_status(request, member_id):
    if not request.user.is_staff:
        messages.error(request, "Access denied.")
        return redirect('dashboard')

    # 1. Identify the Leader and their Unit
    leader_profile = getattr(request.user, 'profile', None) or getattr(request.user, 'profiles', None)
    if hasattr(leader_profile, 'first'):
        leader_profile = leader_profile.first()

    if not leader_profile or not leader_profile.unit:
        messages.error(request, "You must be assigned to a unit to manage members.")
        return redirect('dashboard')

    # 2. Fetch the target member's profile
    target_profile = get_object_or_404(Profile, user_id=member_id)
    target_unit = target_profile.unit

    if not target_unit:
        messages.error(request, "This member is not assigned to any unit.")
        return redirect('members_list')

    # 3. --- HIERARCHY JURISDICTION CHECK ---
    leader_lvl = leader_profile.unit.level    # e.g., 'NATIONAL', 'STATE', 'LG', 'WARD'
    member_lvl = target_unit.level
    can_manage = False

    # National can manage all
    if leader_lvl == 'NATIONAL':
        can_manage = True

    # State can manage their own State members and LGs in that State
    elif leader_lvl == 'STATE':
        if target_unit.state == leader_profile.unit.state:
            if member_lvl in ['STATE', 'LG']:
                can_manage = True

    # LG can manage their own LG members and Wards in that LGA
    elif leader_lvl == 'LG':
        if target_unit.lga == leader_profile.unit.lga:
            if member_lvl in ['LG', 'WARD']:
                can_manage = True

    # --- ADDED WARD LEVEL LOGIC ---
    # A Ward Chairman can manage anyone in their specific Ward unit
    elif leader_lvl == 'WARD':
        if target_unit == leader_profile.unit:
            can_manage = True

    if not can_manage:
        messages.error(request, f"Jurisdiction Error: As a {leader_lvl} leader, you cannot manage this member.")
        return redirect('members_list')

    # 4. --- EXECUTE TOGGLE ---
    reason = request.GET.get('reason', 'No reason provided')
    new_status = not target_profile.is_active

    target_profile.is_active = new_status
    target_user = target_profile.user
    target_user.is_active = new_status

    target_profile.save()
    target_user.save()

    # Log the action for transparency
    status_msg = "Activated" if new_status else f"Suspended ({reason})"
    messages.success(request, f"Successfully updated {target_user.username} to {status_msg}")

    return redirect('members_list')

@login_required
def delete_member_permanent(request, user_id): # Name must match urls.py
    if request.method != 'POST':
        return redirect('members_list')

    # 1. Authority Check
    if not request.user.is_staff:
        messages.error(request, "Unauthorized. Only leaders can delete accounts.")
        return redirect('dashboard')

    # 2. Identify the Leader and the Target
    leader_profile = getattr(request.user, 'profile', None) or getattr(request.user, 'profiles', None)
    if hasattr(leader_profile, 'first'): leader_profile = leader_profile.first()

    target_user = get_object_or_404(User, id=user_id)
    target_profile = getattr(target_user, 'profile', None) or getattr(target_user, 'profiles', None)
    if hasattr(target_profile, 'first'): target_profile = target_profile.first()

    # 3. Hierarchy Protection Logic
    can_delete = False
    leader_lvl = leader_profile.unit.level

    # National can delete anyone except other National Chairmen
    if leader_lvl == 'NATIONAL':
        if not (target_profile and target_profile.unit.level == 'NATIONAL' and 'chairman' in target_profile.position.lower()):
            can_delete = True

    # State can only delete LG/Ward within their state
    elif leader_lvl == 'STATE':
        if target_profile and target_profile.unit.state == leader_profile.unit.state:
            if target_profile.unit.level in ['LG', 'WARD']:
                can_delete = True

    # 4. Final Execution
    if can_delete or request.user.is_superuser:
        username = target_user.username
        target_user.delete() # This removes Profile and User due to CASCADE
        messages.success(request, f"Leader account {username} has been permanently removed.")
    else:
        messages.error(request, "Jurisdiction Error: You do not have the rank to delete this account.")

    return redirect('members_list')

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
def mark_message_read_ajax(request, message_id):
    # Security: Ensure ONLY the recipient can mark this specific message as read
    msg = get_object_or_404(Message, id=message_id, recipient=request.user)

    if not msg.is_read:
        msg.is_read = True
        msg.save()
        return JsonResponse({'status': 'success'})

    return JsonResponse({'status': 'already_read'})

@login_required
def delete_message(request, message_id):
    """Soft delete so the message disappears for the user but remains in DB."""
    message = get_object_or_404(Message, id=message_id)
    if message.recipient == request.user:
        message.recipient_deleted = True
    elif message.sender == request.user:
        message.sender_deleted = True
    message.save()
    return redirect('dashboard')

@login_required
def leader_reply(request, message_id):
    """Only staff/leaders can reply to messages."""
    if not request.user.is_staff:
        messages.error(request, "Access denied. Only leaders can reply.")
        return redirect('dashboard')

    original_msg = get_object_or_404(Message, id=message_id, recipient=request.user)

    if request.method == 'POST':
        reply_body = request.POST.get('body')
        Message.objects.create(
            sender=request.user,
            recipient=original_msg.sender,
            subject=f"Re: {original_msg.subject}",
            body=reply_body
        )
        messages.success(request, "Reply sent successfully.")
        return redirect('dashboard')

@login_required
def inbox(request):
    # Use select_related('sender') to avoid hitting the database
    # multiple times for each sender's name in the template
    messages_received = Message.objects.filter(
        recipient=request.user,
        recipient_deleted=False
    ).select_related('sender').order_by('-timestamp')

    # Optional: Count unread messages for the badge
    unread_count = messages_received.filter(is_read=False).count()

    return render(request, 'accounts/inbox.html', {
        'messages_received': messages_received,
        'unread_count': unread_count
    })

def load_lgas(request):
    state_id = request.GET.get('state_id')
    lgas = LGA.objects.filter(state_id=state_id).order_by('name')
    return JsonResponse(list(lgas.values('id', 'name')), safe=False)

def load_wards(request):
    lga_id = request.GET.get('lga_id')
    wards = Ward.objects.filter(lga_id=lga_id).order_by('name')
    return JsonResponse(list(wards.values('id', 'name')), safe=False)

@login_required
def sent_messages(request):
    # Retrieve memos sent by the current leader
    messages_sent = Message.objects.filter(
        sender=request.user,
        sender_deleted=False
    ).select_related('recipient').order_by('-timestamp')

    return render(request, 'accounts/sent_messages.html', {
        'messages_sent': messages_sent
    })

@login_required
def member_directory(request):
    # Fetch the leader's primary profile
    leader_profile = request.user.profiles.select_related('unit__lga', 'unit__state').first()

    if not leader_profile or not leader_profile.unit:
        messages.error(request, "Access denied. You must be assigned to an official unit.")
        return redirect('dashboard')

    unit = leader_profile.unit
    level = unit.level

    # 1. Start with an optimized QuerySet
    # Use prefetch_related for 'profiles' because it's a Reverse ForeignKey (related_name)
    queryset = User.objects.prefetch_related('profiles__unit__lga', 'profiles__unit__state')

    # 2. Apply Hierarchical Filtering
    if level == 'NATIONAL':
        members = queryset.all()
    elif level == 'STATE':
        # Filter by unit's state
        members = queryset.filter(profiles__unit__state=unit.state)
    elif level == 'LG':
        # Filter by unit's local government
        members = queryset.filter(profiles__unit__lga=unit.lga)
    elif level == 'WARD':
        # Filter by the specific unit itself
        members = queryset.filter(profiles__unit=unit)
    else:
        members = User.objects.none()

    # 3. Clean up the list
    members = members.exclude(id=request.user.id).distinct().order_by('first_name', 'last_name')

    return render(request, 'accounts/members_list.html', {
        'members': members,
        'leader_profile': leader_profile
    })