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
from django.db.models import Q, Sum, Count
from django.urls import reverse_lazy
from django.contrib.auth import get_user_model
from .forms import UserUpdateForm, ProfileUpdateForm, MessageForm, VideoUploadForm, RegistrationForm
from .utils import verify_bank_account
import uuid
from django.core.files.base import ContentFile
from django.shortcuts import render, get_object_or_404, redirect
from .models import Hospital, School, UnitChat, UnitBroadcast, GroupChat, GComment, Committee, CommitteeReport, Comment, OrganizationUnit, Profile, Masjid
from django.utils import timezone
from .forms import MasjidForm, HospitalForm, SchoolForm
from django.template.loader import get_template
from xhtml2pdf import pisa
from django.core.mail import send_mail
from .models import Announcement
from .forms import AnnouncementForm


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
def ulama_landing_page(request):
    """Public portal for the Ulama (Religious) wing."""
    context = {
        'announcements': Announcement.objects.filter(is_active=True, category='ULAMA'),
        'videos': VideoPost.objects.filter(category='ULAMA')[:4],
        'gallery': GalleryImage.objects.filter(category='ULAMA')[:6],
        'title': _("Ulama Wing - JIBWIS")
    }
    return render(request, 'ulama_landing.html', context)

def admin_landing_page(request):
    """Public portal for the Admin (Secretariat) wing."""
    context = {
        'announcements': Announcement.objects.filter(is_active=True, category='ADMIN'),
        'videos': VideoPost.objects.filter(category='ADMIN')[:4],
        'gallery': GalleryImage.objects.filter(category='ADMIN')[:6],
        'title': _("Admin Wing - JIBWIS")
    }
    return render(request, 'admin_landing.html', context)

def fag_landing_page(request):
    """Public portal for the First Aid Group (FAG) wing."""
    context = {
        'announcements': Announcement.objects.filter(is_active=True, category='FAG'),
        'videos': VideoPost.objects.filter(category='FAG')[:4],
        'gallery': GalleryImage.objects.filter(category='FAG')[:6],
        'title': _("First Aid Group - JIBWIS")
    }
    return render(request, 'fag_landing.html', context)

def landing(request):
    """The main global homepage showing a mix of everything."""
    # Showing the 10 most recent announcements from ALL categories
    announcements = Announcement.objects.filter(is_active=True)[:10]
    
    return render(request, 'homepage.html', {
        'announcements': announcements,
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
            is_chairman = 'chairman' or 'director' or 'leader' in pos.lower()

            if lvl == 'NATIONAL' and is_chairman:
                user.is_active = True
                user.is_staff = True
                user.is_leader = True
            elif lvl == 'STATE' and is_chairman:
                user.is_active = False
                user.is_staff = True
                user.is_leader = True
            elif lvl == 'LG' and is_chairman:
                user.is_active = False
                user.is_staff = True
                user.is_leader = True
            elif lvl == 'WARD' or 'UNIT' and is_chairman:
                user.is_active = False
                user.is_staff = True
                user.is_leader = True
            else:
                user.is_active = False
                user.is_staff = False
                user.is_leader = False


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

            status_msg = _("Approved and Active.") if user.is_active else _("Pending Leader Approval.")
            messages.success(request, _(f"Registration Successful! Account {status_msg}"))
            return redirect('login')
        else:
            # If form is invalid, errors will be sent to the template
            messages.error(request, _("Please correct the errors below."))
    else:
        form = RegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})

class CustomLoginView(LoginView):
    template_name = 'login.html'

    def form_valid(self, form):
        user = form.get_user()
        
        # 1. Fixed the profile lookup (Singular 'profile')
        profile = getattr(user, 'profile', None)

        if profile and not profile.is_active:
            messages.error(
                self.request,
                "Your account is pending leader approval. Please contact your Unit Secretary."
            )
            # Re-render the form with the error message
            return self.form_invalid(form)

        # 2. Log metadata safely
        x_fwd = self.request.META.get('HTTP_X_FORWARDED_FOR')
        ip = x_fwd.split(',')[0] if x_fwd else self.request.META.get('REMOTE_ADDR')

        print(_(f"Login Success: {user.username} from IP {ip} at {timezone.now()}"))

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # 3. Secure IP Lookup
        x_fwd = self.request.META.get('HTTP_X_FORWARDED_FOR')
        ip = x_fwd.split(',')[0] if x_fwd else self.request.META.get('REMOTE_ADDR')

        # 4. Axes Security Logic wrapped in Try/Except
        try:
            attempt = AccessAttempt.objects.filter(ip_address=ip).first()
            failures = attempt.failures_since_start if attempt else 0
            limit = 5
            context['remaining_attempts'] = max(0, limit - failures)
            context['show_warning'] = failures > 0
            context['lockout_expires'] = attempt.expiration if attempt else None
        except Exception:
            # Fallback values if Axes is not configured or table missing
            context['remaining_attempts'] = 5
            context['show_warning'] = False

        return context

    def get_success_url(self):
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
    is_staff = request.user.is_staff

    context = {
        'profiles': queryset.order_by('user__first_name'),
        'states': State.objects.all(),
        'categories': OrganizationUnit.CATEGORY_CHOICES,
        'is_staff': is_staff,
    }
    return render(request, 'leader_directory.html', context)


@login_required
def dashboard(request):
    # 1. PROFILE & UNIT GUARANTEE
    user_profile = getattr(request.user, 'profile', None)
    
    if not user_profile:        
        u_cat = getattr(request.user, 'category', 'ADMIN')
        u_lvl = getattr(request.user, 'level', 'NATIONAL')
        
        target_unit, created = OrganizationUnit.objects.get_or_create(
            category=u_cat, 
            level=u_lvl,
            defaults={'name': f"System {u_lvl.title()} {u_cat.title()} Unit"}
        )

        user_profile = Profile.objects.create(
            user=request.user,
            unit=target_unit,
            is_leader=True,
            is_active=True
        )
        messages.success(request, _(f"Welcome! Your {u_cat} dashboard is now active."))

    unit = user_profile.unit
    leader_profile = user_profile # Using the same guaranteed object

    if not user_profile.is_active:
        return render(request, 'pending_approval.html')

    # 2. INSTITUTION COUNTS (New Logic)
    # We filter these by the leader's unit to ensure they only see their local data
    masjids = Masjid.objects.filter(unit=unit)
    schools = School.objects.filter(unit=unit)
    hospitals = Hospital.objects.filter(unit=unit)


    # 4. COMMITTEE LOGIC
    if request.user.is_staff or user_profile.is_leader:
        if unit and unit.level == 'NATIONAL':
            if unit.category == 'ADMIN':
                committees = Committee.objects.all().order_by('-created_at')
            else:
                committees = Committee.objects.filter(unit__category=unit.category).order_by('-created_at')
        elif unit:
            committees = Committee.objects.filter(unit=unit).order_by('-created_at')
        else:
            committees = Committee.objects.none()
    else:
        committees = Committee.objects.filter(members=request.user).order_by('-created_at')
    
    # 4. GROUP CHAT LOGIC
    if request.user.is_staff or user_profile.is_leader:
        if unit and unit.level == 'NATIONAL':
            if unit.category == 'ADMIN':
                groupchats = GroupChat.objects.all().order_by('-created_at')
            else:
                groupchats = GroupChat.objects.filter(unit__category=unit.category).order_by('-created_at')
        elif unit:
            groupchats = GroupChat.objects.filter(unit=unit).order_by('-created_at')
        else:
            groupchats = GroupChat.objects.none()
    else:
        groupchats = GroupChat.objects.filter(members=request.user).order_by('-created_at')


    # 5. ANNOUNCEMENTS
    announcements = Announcement.objects.filter(
        Q(unit=unit) | 
        Q(unit__category=unit.category, unit__level='NATIONAL') | 
        Q(unit__isnull=True),
        is_active=True
    ).distinct().order_by('-created_at')

    # 6. PAYROLL & MEMBER DATA
    members, unit_leaders, member_chat_feed = [], [], []
    total_spent = 0
    
    is_leader = user_profile.is_leader or request.user.is_staff

    if is_leader:
        total_spent = PayrollRecord.objects.filter(
            member__profile__unit=unit,
            status='success'
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        members = Profile.objects.filter(unit=unit, is_active=True).exclude(user=request.user)
        # Fetching members pending unit verification
        pending = Profile.objects.filter(unit=unit, is_active=False) 
        pending_count = pending.count()
    else:
        unit_leaders = Profile.objects.filter(unit=unit, is_leader=True).select_related('user')
        member_chat_feed = UnitChat.objects.filter(
            Q(recipients=request.user) | Q(sender=request.user)
        ).distinct().order_by('-timestamp')
        pending, pending_count = [], 0

    context = {
        'user_profile': user_profile,
        'leader_profile': leader_profile,
        'unit': unit,
        'members': members,
        'committees': committees,
        'groupchats': groupchats,
        'pending': pending,
        'pending_count': pending_count,
        'unit_leaders': unit_leaders,
        'total_spent': total_spent,
        'announcements': announcements,
        'chats': member_chat_feed,
        
        # New Context Variables for Institutions
        'masjids': masjids,
        'schools': schools,
        'hospitals': hospitals,
    }
    
    template = 'dashboard.html' if is_leader else 'member_dashboard.html'
    return render(request, template, context)

@login_required
def member_dashboard(request):
    user_profile = request.user.profile
    
    # 1. Fetch directives for their unit
    chats = Message.objects.filter(
        recipient=request.user,
        # Optional: only show messages from leaders
        sender__profile__is_leader=True 
    ).order_by('-timestamp')

    # 2. Fetch committees where the user is a member
    # This looks at the ManyToManyField in your Committee model
    user_committees = Committee.objects.filter(
        members=request.user
    ).select_related('unit', 'team_lead')

    return render(request, 'member_dashboard.html', {
        'chats': chats,
        'user_committees': user_committees,
        'leader_profile': user_profile # For the unit info header
    })

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
    members = User.objects.all().prefetch_related('profile__unit', 'profile__unit__state')

    # 3. Apply Hierarchy Filter (Jurisdiction)
    if not request.user.is_superuser:
        if not leader_profile or not leader_profile.unit:
            # If a user has no unit, they see nothing for security
            members = User.objects.none()
        else:
            lvl = leader_profile.unit.level

            if lvl == 'STATE':
                # State Leaders see everyone in their specific State
                members = members.filter(profile__unit__state=leader_profile.unit.state)

            elif lvl == 'LG':
                # LG Leaders see everyone in their specific LGA
                members = members.filter(profile__unit__lga=leader_profile.unit.lga)

            elif lvl == 'WARD' or lvl == 'UNIT':
                # Ward Leaders only see their own Branch
                members = members.filter(profile__unit=leader_profile.unit)

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
        members = members.filter(profile__unit__category=category_filter)

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
        messages.error(request, _("Access denied. Only leaders can approve members."))
        return redirect('dashboard')

    # 2. Identify the Leader
    leader_profile = getattr(request.user, 'profile', None) or getattr(request.user, 'profiles', None)
    if hasattr(leader_profile, 'first'):
        leader_profile = leader_profile.first()

    if not leader_profile or not leader_profile.unit:
        messages.error(request, _("You are not assigned to a unit."))
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
        messages.error(request, _("This member has not been assigned to a unit yet."))
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
    elif leader_lvl == 'WARD' or leader_lvl == 'UNIT':
        # Ward Chairmen can only approve members in their exact same Ward
        if member_unit == leader_profile.unit:
            can_approve = True

    if not can_approve:
        messages.error(request, _(f"Jurisdiction Error: As a {leader_lvl} leader, you cannot manage this member."))
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

        messages.success(request, _(f"Member {member_user.get_full_name() or member_user.username} has been approved."))

    return redirect('members_list')

# --- 3. PAYROLL & DATA ---

@login_required
def export_members_excel(request):
    # 1. Get the Leader's Profile using the plural 'profiles'
    leader_profile = request.user.profile

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
    members = User.objects.all().prefetch_related('profile__unit')

    if lvl == 'STATE':
        members = members.filter(profile__unit__state=leader_profile.unit.state)
    elif lvl == 'LG':
        members = members.filter(profile__unit__lga=leader_profile.unit.lga)

    # 5. Populate Data
    for m in members.distinct():
        p = m.profile
        ws.append([
            m.username,
            m.get_full_name(),
            m.email,
            p.position if p else "N/A",
            p.unit.level if p and p.unit else "N/A",
           _("Active") if m.is_active else _("Suspended")
        ])

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename=JIBWIS_Directory.xlsx'
    wb.save(response)

    return response

@login_required
def payroll_history(request):
    leader_profile = request.user.profile

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
    leader_profile = request.user.profile
    recipient_profile = recipient.profile

    # Ensure leader has a profile and can only message those they oversee
    if not leader_profile or not leader_profile.unit:
        messages.error(request, _("You must be assigned to a unit to send official memos."))
        return redirect('dashboard')

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
    # Ensure only Staff or Leaders can upload
    if not (request.user.is_staff or request.user.profile.is_leader):
        messages.error(request, _("You do not have permission to upload videos."))
        return redirect('dashboard')

    if request.method == 'POST':
        form = VideoUploadForm(request.POST, request.FILES)
        if form.is_valid():
            # 1. Commit=False allows us to add the creator manually
            video = form.save(commit=False)
            video.creator = request.user 
            
            # 2. Save the video (this triggers the thumbnail generator in models.py)
            video.save()
            
            # 3. Handle ManyToMany if your form has tags or members
            form.save_m2m()

            messages.success(request, _("Video published to the {cat} feed.")).format(
                cat=video.get_category_display()
            )
            
            # 4. Redirect to the specific landing page based on the video category
            if video.category == 'ULAMA':
                return redirect('ulama_landing')
            elif video.category == 'FAG':
                return redirect('fag_landing')
            else:
                return redirect('admin_landing')
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
    leader_profile = request.user.profile
    if not leader_profile or not leader_profile.unit:
        messages.error(request, _("Access Denied."))
        return redirect('dashboard')

    leader_unit = leader_profile.unit
    category = leader_unit.category
    level = leader_unit.level  # Assumes your model has 'level'
    query = request.GET.get('q', '')

    # Base Query: Start with everyone in the same category
    personnel = User.objects.filter(profile__unit__category=category).distinct().exclude(id=request.user.id)

    # Apply Level Restrictions
    if level == 'STATE':
        # State leaders only see personnel within their specific state
        personnel = personnel.filter(profile__unit__state=leader_unit.state)
    elif level == 'LGA':
        # LGA leaders only see personnel within their specific LGA
        personnel = personnel.filter(profile__unit__lga=leader_unit.lga)
    elif level == 'WARD' or level == 'UNIT':
        # Ward leaders only see personnel in their specific ward
        personnel = personnel.filter(profile__unit=leader_unit)
    # If level is 'NATIONAL', no extra filter is applied (they see everyone)

    # Apply Search Filter
    if query:
        personnel = personnel.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(profile__unit__name__icontains=query)
        )

    context = {
        'members': personnel.order_by('profile__unit__level', 'profile__unit__name'),
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

        messages.success(request, _(f"Successfully initiated {processed_count} real-time transfers."))
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
    results = User.objects.all().prefetch_related('profile__unit')

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
        results = results.filter(profile__unit__category=category)

    # 3. Filter by Organizational Level (NATIONAL, STATE, etc.)
    if level:
        results = results.filter(profile__unit__level=level)

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
        messages.error(request, _("Access denied. Only leaders can send official replies."))
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

        messages.success(request, _("Reply successfully sent!"))
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

        messages.success(request, _("Your report has been submitted to the National Disciplinary Committee."))
        return redirect('dashboard')

    return redirect('dashboard')

@login_required
def disciplinary_admin(request):
    # Security Check: Only National level staff can see this
    profile = request.user.profile
    if not request.user.is_staff or profile.unit.level != 'NAT':
        messages.error(request, _("Access Denied: High-level Clearance Required."))
        return redirect('dashboard')

    reports = DisciplinaryReport.objects.all().order_by('-created_at')

    return render(request, 'disciplinary_list.html', {'reports': reports})

@login_required
def edit_profile(request):
    profile = request.user.profile
    
    u_form = UserUpdateForm(instance=request.user)
    p_form = ProfileUpdateForm(instance=profile)

    if request.method == 'POST':
        form_type = request.POST.get('form_type')

        # --- OPTION 1: Update Personal Information ---
        if form_type == 'personal_update':
            u_form = UserUpdateForm(request.POST, instance=request.user)
            p_form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)
            
            if u_form.is_valid() and p_form.is_valid():
                u_form.save()
                p_form.save()
                messages.success(request, _("Personal records updated successfully!"))
                return redirect('edit_profile')

    return render(request, 'accounts/edit_profile.html', {
        'u_form': u_form,
        'p_form': p_form
    })

@login_required
def toggle_member_status(request, member_id):
    if not request.user.is_staff:
        messages.error(request, _("Access denied."))
        return redirect('dashboard')

    # 1. Identify the Leader and their Unit
    leader_profile = getattr(request.user, 'profile', None) or getattr(request.user, 'profiles', None)
    if hasattr(leader_profile, 'first'):
        leader_profile = leader_profile.first()

    if not leader_profile or not leader_profile.unit:
        messages.error(request, _("You must be assigned to a unit to manage members."))
        return redirect('dashboard')

    # 2. Fetch the target member's profile
    target_profile = get_object_or_404(Profile, user_id=member_id)
    target_unit = target_profile.unit

    if not target_unit:
        messages.error(request, _("This member is not assigned to any unit."))
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
    elif leader_lvl == 'WARD' or leader_lvl == 'UNIT':
        if target_unit == leader_profile.unit:
            can_manage = True

    if not can_manage:
        messages.error(request, _(f"Jurisdiction Error: As a {leader_lvl} leader, you cannot manage this member."))
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
    status_msg =_("Activated")if new_status else _(f"Suspended ({reason})")
    messages.success(request, _(f"Successfully updated {target_user.username} to {status_msg}"))

    return redirect('members_list')

@login_required
def delete_member_permanent(request, user_id): # Name must match urls.py
    if request.method != 'POST':
        return redirect('members_list')

    # 1. Authority Check
    if not request.user.is_staff:
        messages.error(request, _("Unauthorized. Only leaders can delete accounts."))
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
        if not (target_profile and target_profile.unit.level == 'NATIONAL' and 'chairman' or 'director' in target_profile.position.lower()):
            can_delete = True

    # State can only delete LG/Ward within their state
    elif leader_lvl == 'STATE':
        if target_profile and target_profile.unit.state == leader_profile.unit.state:
            if target_profile.unit.level in ['LG', 'WARD', 'UNIT']:
                can_delete = True

    # 4. Final Execution
    if can_delete or request.user.is_superuser:
        username = target_user.username
        target_user.delete() # This removes Profile and User due to CASCADE
        messages.success(request, _(f"Leader account {username} has been permanently removed."))
    else:
        messages.error(request, _("Jurisdiction Error: You do not have the rank to delete this account."))

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
    return redirect('inbox')

@login_required
def leader_reply(request, message_id):
    """Only staff/leaders can reply to messages."""
    if not request.user.is_staff:
        messages.error(request, _("Access denied. Only leaders can reply."))
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
        messages.success(request, _("Reply sent successfully."))
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
    leader_profile = request.user.profile.select_related('unit__lga', 'unit__state').first()

    if not leader_profile or not leader_profile.unit:
        messages.error(request, _("Access denied. You must be assigned to an official unit."))
        return redirect('dashboard')

    unit = leader_profile.unit
    level = unit.level

    # 1. Start with an optimized QuerySet
    # Use prefetch_related for 'profiles' because it's a Reverse ForeignKey (related_name)
    queryset = User.objects.prefetch_related('profile__unit__lga', 'profile__unit__state')

    # 2. Apply Hierarchical Filtering
    if level == 'NATIONAL':
        members = queryset.all()
    elif level == 'STATE':
        # Filter by unit's state
        members = queryset.filter(profile__unit__state=unit.state)
    elif level == 'LG':
        # Filter by unit's local government
        members = queryset.filter(profile__unit__lga=unit.lga)
    elif level == 'WARD':
        # Filter by the specific unit itself
        members = queryset.filter(profile__unit=unit)
    else:
        members = User.objects.none()

    # 3. Clean up the list
    members = members.exclude(id=request.user.id).distinct().order_by('first_name', 'last_name')

    return render(request, 'accounts/members_list.html', {
        'members': members,
        'leader_profile': leader_profile
    })

def delete_chat_message(request, chat_id):
    """Deletes a single directive bubble from the feed."""
    if request.method == 'POST':
        # Safety check: only the sender can delete their own message
        chat = get_object_or_404(UnitChat, id=chat_id, sender=request.user)
        chat.delete()
        messages.success(request, _("Directive removed."))
    return redirect('members_list')

def clear_unit_chat(request):
    """Wipes the entire command feed history for the logged-in leader."""
    if request.method == 'POST':
        UnitChat.objects.filter(sender=request.user).delete()
        messages.success(request, _("Command feed has been reset."))
    return redirect('members_list')

def bulk_voice_send(request):
    if request.method == 'POST':
        # Get the list of IDs sent from the hidden inputs in the Voice Modal
        member_ids = request.POST.getlist('selected_members')
        voice_file = request.FILES.get('voice_file')

        if not member_ids:
            messages.warning(request, _("No personnel selected."))
            return redirect('members_list')

        if voice_file:
            # Create the broadcast record
            broadcast = UnitBroadcast.objects.create(
                sender=request.user,
                voice_recording=voice_file,
                message_type='VOICE'
            )
            # Add all selected members to the ManyToMany field
            broadcast.recipients.set(member_ids)
            
            messages.success(request, _(f"Voice directive successfully dispatched to {len(member_ids)} members."))
        else:
            messages.error(request, _("Voice recording failed. Please try again."))

    return redirect('members_list')

def bulk_message_send(request):
    if request.method == 'POST':
        member_ids = request.POST.getlist('selected_members')
        body = request.POST.get('body')
        attachment = request.FILES.get('attachment')

        if not member_ids:
            messages.error(request, _("Selection Error: No personnel were selected for this broadcast."))
            return redirect('members_list')

        try:
            # 1. Create the instance first
            broadcast = UnitChat.objects.create(
                sender=request.user,
                text_content=body,
                file_attachment=attachment
            )
            
            # 2. Use .set() for ManyToMany after the ID is created
            broadcast.recipients.set(member_ids)
            
            messages.success(request, _(f"Directive dispatched to {len(member_ids)} personnel."))
        except Exception as e:
            # This will show you the exact error in your terminal
            print(_(f"Broadcast Error: {e}"))
            messages.error(request, _("Server Error: Could not process the broadcast."))
            
    return redirect('members_list')

@login_required
def send_to_leader(request):
    if request.method == 'POST':
        body = request.POST.get('body')
        user_profile = request.user.profile
        
        # 1. Logic: If I am a member, find my unit leader.
        # 2. Logic: If I AM the leader, find the leader of my PARENT unit (e.g., State -> National)
        target_unit = user_profile.unit
        if user_profile.is_leader and user_profile.unit.parent:
            target_unit = user_profile.unit.parent

        leader_profile = Profile.objects.filter(
            unit=target_unit, 
            is_leader=True
        ).exclude(user=request.user).first() # Ensure I don't message myself

        if leader_profile:
            Message.objects.create(
                sender=request.user,
                recipient=leader_profile.user,
                body=body,
                subject=_(f"Official Correspondence: {user_profile.unit.name}")
            )
            messages.success(request, _(f"Message escalated to {leader_profile.user.get_full_name()}."))
        else:
            messages.error(request, _("No superior leader found for this unit level."))
        
    return redirect('dashboard')

@login_required
def create_committee(request):
    # 1. PREVENT CLONING: Check for ANY existing profile using plural related_name
    # Using .first() ensures we get one if it exists, and None if it doesn't
    user_profile = request.user.profile
    
    # 2. AUTO-INITIALIZE: Only if the user has NO profile at all
    if not user_profile:        
        u_cat = getattr(request.user, 'category', 'ADMIN') 
        u_lvl = getattr(request.user, 'level', 'NATIONAL')
        u_state = getattr(request.user, 'state', None)
        u_lga = getattr(request.user, 'lga', None)

        # Find the UNIT matching their registration
        target_unit = OrganizationUnit.objects.filter(
            category=u_cat,
            level=u_lvl,
            state=u_state,
            lga=u_lga
        ).first()

        # Create unit if it's a completely new location/category combo
        if not target_unit:
            target_unit = OrganizationUnit.objects.create(
                category=u_cat,
                level=u_lvl,
                state=u_state,
                lga=u_lga,
                name=f"{u_lvl.title()} {u_cat.title()} Unit"
            )

        # Final Profile creation (Only happens once per user now)
        user_profile = Profile.objects.create(
            user=request.user, 
            unit=target_unit, 
            is_leader=True,
            is_active=True
        )

    # 3. SCOPED FILTERING
    current_unit = user_profile.unit
    
    if current_unit.level == 'NATIONAL':
        # National Leaders see all members within their CATEGORY (e.g., all FAG members)
        available_members = Profile.objects.filter(
            unit__category=current_unit.category,
            is_active=True
        ).select_related('user', 'unit')
    else:
        # State/LG/Ward Leaders see members in their specific physical Unit
        available_members = Profile.objects.filter(
            unit=current_unit, 
            is_active=True
        ).select_related('user', 'unit')

    # 4. Handle POST
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        team_lead_id = request.POST.get('team_lead')
        member_ids = request.POST.getlist('members')

        if name and team_lead_id:
            # Create the committee object
            committee = Committee.objects.create(
                name=name,
                description=description,
                unit=current_unit,
                team_lead_id=team_lead_id,
                creator=request.user  # <--- ADD THIS LINE HERE
            )

            # Add the members
            if member_ids:
                committee.members.set(member_ids) 

            messages.success(request, _(f"Committee '{name}' created successfully!"))
            return redirect('committee_list')
        else:
            messages.error(request, _("Name and Team Lead are required."))

    return render(request, 'create_committee.html', {
        'available_members': available_members,
        'user_profile': user_profile,
        'unit': current_unit
    })
    
@login_required
def delete_committee(request, pk):
    committee = get_object_or_404(Committee, pk=pk)
    
    user_profile = request.user.profile

    # Security Check: Only allow if it's their unit or they are a superuser
    if committee.unit == user_profile.unit or user_profile.is_superuser:
        committee.delete()
        messages.success(request, _("Committee deleted."))
    else:
        messages.error(request, _("You do not have permission to delete this."))
        
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))    

@login_required
def committee_list(request):
    user_profile = request.user.profile
    unit = user_profile.unit
    
    # 1. Get Sort Preference
    sort_by = request.GET.get('sort', '-created_at')
    
    # 2. Get Committees based on Hierarchy
    if unit.level == 'NATIONAL' and unit.category == 'ADMIN':
        # Admin sees everything
        base_committees = Committee.objects.all()
    elif unit.level == 'NATIONAL':
        # National Ulama/FAG see their department's committees
        base_committees = Committee.objects.filter(unit__category=unit.category)
    else:
        # State/Local see their specific unit's committees OR ones they belong to
        base_committees = Committee.objects.filter(
            Q(unit=unit) | Q(members=request.user)
        ).distinct()

    # Pre-fetch for speed
    base_committees = base_committees.order_by(sort_by).select_related('unit').prefetch_related('members')

    # 3. Group them strictly by the Unit Category
    grouped = {}
    for cmd in base_committees:
        # Get category display name from the Unit
        if cmd.unit:
            cat_name = cmd.unit.get_category_display()
        else:
            cat_name = _("General / Unassigned")

        if cat_name not in grouped:
            grouped[cat_name] = []
        grouped[cat_name].append(cmd)

    return render(request, 'committee_list.html', {
        'grouped_committees': grouped, # Make sure this matches your HTML loop
        'unit': unit,
        'user_profile': user_profile,
        'current_sort': sort_by
    })
    
@login_required
def committee_detail(request, pk):
    committee = get_object_or_404(Committee, pk=pk)
    user_profile = request.user.profile
    # Check if the user is a member, the creator, or a high-level admin
    is_member = request.user in committee.members.all()
    is_creator = request.user == committee.creator
    is_admin = user_profile.unit.category == 'ADMIN'
    
    if not (is_member or is_creator or is_admin):
        messages.error(request, _("You do not have access to this committee's details."))
        return redirect('dashboard')

    # Fetch related data
    reports = committee.reports.all().order_by('-uploaded_at')
    comments = committee.comments.all().order_by('created_at')

    return render(request, 'committee_detail.html', {
        'committee': committee,
        'reports': reports,
        'comments': comments,
        'is_lead': request.user == committee.team_lead
    })

@login_required
def upload_committee_report(request, committee_pk):
    committee = get_object_or_404(Committee, pk=committee_pk)
    
    # Only allow the Creator or Team Lead to upload
    if request.user != committee.creator and request.user != committee.team_lead:
        messages.error(request, _("Permission denied."))
        return redirect('committee_detail', pk=committee_pk)

    if request.method == 'POST' and request.FILES.get('report_file'):
        report_file = request.FILES['report_file']
        title = request.POST.get('title') or report_file.name
        
        CommitteeReport.objects.create(
            committee=committee,
            title=title,
            file=report_file,
            uploaded_by=request.user
        )
        messages.success(request, _("Report uploaded successfully."))
        
    return redirect('committee_detail', pk=committee_pk)

@login_required
def join_committee(request, pk):
    if request.method == 'POST':
        committee = get_object_or_404(Committee, pk=pk)
        # Check if user is already in the committee
        if request.user not in committee.members.all():
            committee.members.add(request.user)
            messages.success(request, _(f"You have successfully joined the {committee.name} committee!"))
        else:
            messages.info(request, _("You are already a member of this committee."))
    return redirect('committee_list')

@login_required
def leave_committee(request, pk):
    if request.method == 'POST':
        committee = get_object_or_404(Committee, pk=pk)
        if request.user in committee.members.all():
            committee.members.remove(request.user)
            messages.info(request, _(f"You have left the {committee.name} committee."))
        else:
            messages.error(request, _("You are not a member of this committee."))
    return redirect('committee_list')

@login_required
def create_announcement(request):
    user_profile = request.user.profile
    
    if request.method == 'POST':
        form = AnnouncementForm(request.POST)
        if form.is_valid():
            announcement = form.save(commit=False)
            announcement.unit = user_profile.unit
            announcement.category = user_profile.unit.category 
            announcement.save()
            messages.success(request, _("Announcement published successfully!"))
            return redirect('dashboard')
        else:
            # DEBUG: This prints the exact error to your CMD/Terminal
            print(form.errors) 
            messages.error(request, _("Please correct the errors below."))
    else:
        form = AnnouncementForm()
    
    return render(request, 'update_announcement.html', {
        'form': form,
        'announcement': None 
    })

@login_required
def delete_announcement(request, pk):
    # Only allow deletion via POST for security
    if request.method == 'POST':
        announcement = get_object_or_404(Announcement, pk=pk)
        user_profile = request.user.profile
        
        # Check if the user is a superuser or belongs to the same unit
        if request.user.is_superuser or announcement.unit == user_profile.unit:
            announcement.delete()
            messages.success(request, _("Announcement deleted."))
        else:
            messages.error(request, _("You do not have permission to delete this."))
            
    return redirect('dashboard')

@login_required
def upload_gallery_image(request):
    user_profile = request.user.profile
    
    if request.method == 'POST':
        title = request.POST.get('title')
        image_file = request.FILES.get('image_file')
        
        if image_file:
            GalleryImage.objects.create(
                title=title,
                image=image_file,
                category=user_profile.unit.category, # Auto-categorize
                order=0 # Default order
            )
            messages.success(request, _("Image added to gallery."))
            return redirect('dashboard')
            
    return render(request, 'upload_gallery.html')

@login_required
def delete_gallery_image(request, pk):
    image = get_object_or_404(GalleryImage, pk=pk)
    user_profile = request.user.profile
    # Security Check: Only allow if it's their unit or they are a superuser
    if image.unit == user_profile.unit or user_profile.is_superuser:
        image.delete()
        messages.success(request, _("Gallery Image deleted."))
    else:
        messages.error(request, _("You do not have permission to delete this."))
        
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))

@login_required
def add_comment(request, pk):
    committee = get_object_or_404(Committee, pk=pk)
    
    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            # We use the 'committee' object and 'request.user' to link the comment
            Comment.objects.create(
                committee=committee,
                text=content
            )
            messages.success(request, _("Comment added successfully."))
        else:
            messages.error(request, _("Comment cannot be empty."))
            
    return redirect('committee_detail', pk=pk)

@login_required
def gallery_list(request):
    user_profile = request.user.profile
    # Filter images by the leader's unit category
    images = GalleryImage.objects.filter(category=user_profile.unit.category).order_by('-created_at')
    
    return render(request, 'gallery_list.html', {
        'images': images,
        'category_name': user_profile.unit.get_category_display()
    })


@login_required
def school_dashboard(request):
    user_profile = request.user.profile
    unit = user_profile.unit
    schools = School.objects.filter(unit=unit)
    
    # Calculate Total Statistics for the Unit
    stats = schools.aggregate(
        total_males=Sum('total_male_students'),
        total_females=Sum('total_female_students'),
        total_staff=Sum('total_teachers')
    )
    
    return render(request, 'institutions/list.html', {
        'schools': schools,
        'stats': stats,
        'unit': unit
    })

@login_required
def hospital_list(request):
    user_profile = request.user.profile
    # Only show hospitals within the leader's specific unit (State/Ward)
    hospitals = Hospital.objects.filter(unit=user_profile.unit)
    return render(request, 'institutions/list.html', {'hospitals': hospitals})

@login_required
def create_hospital(request):
    user_profile = request.user.profile
    if user_profile.unit.level != 'WARD' and user_profile.unit.category != 'ADMIN':
        messages.error(request, _("Only the Ward Chairman (Admin) can register Hospitals."))
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = HospitalForm(request.POST)
        if form.is_valid():
            hospital = form.save(commit=False)
            hospital.unit = user_profile.unit # Security: Auto-assign to leader's unit
            hospital.save()
            messages.success(request, _(f"Hospital '{hospital.name}' has been registered."))
            return redirect('hospital_list')
    else:
        form = HospitalForm()
    return render(request, 'institutions/form.html', {'form': form})


@login_required
def masjid_list(request):
    user_profile = request.user.profile
    # Fetch only the masjids belonging to the logged-in leader's unit
    unit = user_profile.unit
    masjids = Masjid.objects.filter(unit=unit).order_by('name')
    
    return render(request, 'institutions/list.html', {
        'masjids': masjids,
        'unit': unit
    })
    
@login_required
def export_unit_report_pdf(request):
    user_profile = request.user.profile
    unit = user_profile.unit
    context = {
        'unit': unit,
        'masjids': Masjid.objects.filter(unit=unit),
        'schools': School.objects.filter(unit=unit),
        'hospitals': Hospital.objects.filter(unit=unit),
        'date': timezone.now(),
        'leader': user_profile.get_full_name()
    }
    
    # Render HTML to PDF
    template = get_template('unit_report_pdf.html')
    html = template.render(context)
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Report_{unit.name}.pdf"'
    
    # Create PDF
    pisa_status = pisa.CreatePDF(html, dest=response)
    
    if pisa_status.err:
        return HttpResponse('We had some errors <pre>' + html + '</pre>')
    return response

@login_required
def create_masjid(request):
    user_profile = request.user.profile
    
    if user_profile.unit.level != 'WARD' or user_profile.unit.category != 'ULAMA':
        messages.error(request, _("Only the Ward Chairman (ULAMA) can register Masjids."))
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = MasjidForm(request.POST)
        if form.is_valid():
            masjid = form.save(commit=False)
            # Link to the leader's unit automatically
            masjid.unit = user_profile.unit
            masjid.save()
            messages.success(request, _(f"Masjid '{masjid.name}' registered successfully."))
            return redirect('masjid_list')
    else:
        form = MasjidForm()
    return render(request, 'institutions/form.html', {'form': form, 'title': 'Register Masjid'})

@login_required
def create_school(request):
    user_profile = request.user.profile
    
    if user_profile.unit.level != 'WARD' and user_profile.unit.category != 'ULAMA':
        messages.error(request, _("Only the Ward Chairman (ULAMA) can register Schools."))
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = SchoolForm(request.POST)
        if form.is_valid():
            school = form.save(commit=False)
            # Link to the leader's unit automatically
            school.unit = user_profile.unit
            school.save()
            messages.success(request, _(f"School '{school.name}' registered successfully."))
            return redirect('school_dashboard')
    else:
        form = SchoolForm()
    return render(request, 'institutions/form.html', {'form': form, 'title': 'Register School'})

@login_required
def school_list(request):
    user_profile = request.user.profile
    # Fetch only the masjids belonging to the logged-in leader's unit
    unit = user_profile.unit.category
    schools = School.objects.filter(unit=unit).order_by('name')
    
    return render(request, 'institutions/list.html', {
        'schools': schools,
        'unit': unit
    })

@login_required
def create_groupchat(request):
    # 1. PREVENT CLONING: Check for ANY existing profile using plural related_name
    # Using .first() ensures we get one if it exists, and None if it doesn't
    user_profile = request.user.profile
    
    # 2. AUTO-INITIALIZE: Only if the user has NO profile at all
    if not user_profile:        
        u_cat = getattr(request.user, 'category', 'ADMIN') 
        u_lvl = getattr(request.user, 'level', 'NATIONAL')
        u_state = getattr(request.user, 'state', None)
        u_lga = getattr(request.user, 'lga', None)

        # Find the UNIT matching their registration
        target_unit = OrganizationUnit.objects.filter(
            category=u_cat,
            level=u_lvl,
            state=u_state,
            lga=u_lga
        ).first()

        # Create unit if it's a completely new location/category combo
        if not target_unit:
            target_unit = OrganizationUnit.objects.create(
                category=u_cat,
                level=u_lvl,
                state=u_state,
                lga=u_lga,
                name=f"{u_lvl.title()} {u_cat.title()} Unit"
            )

        # Final Profile creation (Only happens once per user now)
        user_profile = Profile.objects.create(
            user=request.user, 
            unit=target_unit, 
            is_leader=True,
            is_active=True
        )

    # 3. SCOPED FILTERING
    current_unit = user_profile.unit
    
    if current_unit.level == 'NATIONAL':
        # National Leaders see all members within their CATEGORY (e.g., all FAG members)
        available_members = Profile.objects.filter(
            unit__category=current_unit.category,
            is_active=True
        ).select_related('user', 'unit')
    else:
        # State/LG/Ward Leaders see members in their specific physical Unit
        available_members = Profile.objects.filter(
            unit=current_unit, 
            is_active=True
        ).select_related('user', 'unit')

    # 4. Handle POST
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        team_lead_id = request.POST.get('team_lead')
        member_ids = request.POST.getlist('members')

        if name and team_lead_id:
            # Create the groupchat object
            groupchat = GroupChat.objects.create(
                name=name,
                description=description,
                unit=current_unit,
                team_lead_id=team_lead_id,
                creator=request.user
            )

            # Add the members
            if member_ids:
                groupchat.members.set(member_ids) 

            messages.success(request, _(f"Groupchat '{name}' created successfully!"))
            return redirect('groupchat_list')
        else:
            messages.error(request, _("Name and Team Lead are required."))

    return render(request, 'create_groupchat.html', {
        'available_members': available_members,
        'user_profile': user_profile,
        'unit': current_unit
    })
    
@login_required
def delete_groupchat(request, pk):
    groupchat = get_object_or_404(GroupChat, pk=pk)
    user_profile = request.user.profile
    
    # Security Check: Only allow if it's their unit or they are a superuser
    if groupchat.unit == user_profile.unit or user_profile.is_superuser:
        groupchat.delete()
        messages.success(request, _("Groupchat deleted."))
    else:
        messages.error(request, _("You do not have permission to delete this."))
        
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))    

@login_required
def groupchat_list(request):
    user_profile = request.user.profile
    unit = user_profile.unit
    
    # 1. Get Sort Preference
    sort_by = request.GET.get('sort', '-created_at')
    
    # 2. Get groupchats based on Hierarchy
    if unit.level == 'NATIONAL' and unit.category == 'ADMIN':
        # Admin sees everything
        base_groupchats = GroupChat.objects.all()
    elif unit.level == 'NATIONAL':
        # National Ulama/FAG see their department's groupchats
        base_groupchats = GroupChat.objects.filter(unit__category=unit.category)
    else:
        # State/Local see their specific unit's groupchats OR ones they belong to
        base_groupchats = GroupChat.objects.filter(
            Q(unit=unit) | Q(members=request.user)
        ).distinct()

    # Pre-fetch for speed
    base_groupchats = base_groupchats.order_by(sort_by).select_related('unit').prefetch_related('members')

    # 3. Group them strictly by the Unit Category
    grouped = {}
    for cmd in base_groupchats:
        # Get category display name from the Unit
        if cmd.unit:
            cat_name = cmd.unit.get_category_display()
        else:
            cat_name = _("General / Unassigned")

        if cat_name not in grouped:
            grouped[cat_name] = []
        grouped[cat_name].append(cmd)

    return render(request, 'groupchat_list.html', {
        'grouped_groupchats': grouped, # Make sure this matches your HTML loop
        'unit': unit,
        'user_profile': user_profile,
        'current_sort': sort_by
    })
    
@login_required
def groupchat_detail(request, pk):
    groupchat = get_object_or_404(GroupChat, pk=pk)
    
    # Check if the user is a member, the creator, or a high-level admin
    is_member = request.user in groupchat.members.all()
    is_creator = request.user == groupchat.creator
    is_admin = request.user.profile.unit.category == 'ADMIN'
    
    if not (is_member or is_creator or is_admin):
        messages.error(request, _("You do not have access to this groupchat's details."))
        return redirect('dashboard')

    # Fetch related data
    g_comments = groupchat.g_comments.all().order_by('created_at')

    return render(request, 'groupchat_detail.html', {
        'groupchat': groupchat,
        'g_comments': g_comments,
        'is_lead': request.user == groupchat.team_lead
    })

@login_required
def join_groupchat(request, pk):
    if request.method == 'POST':
        groupchat = get_object_or_404(GroupChat, pk=pk)
        # Check if user is already in the groupchat
        if request.user not in groupchat.members.all():
            groupchat.members.add(request.user)
            messages.success(request, _(f"You have successfully joined the {groupchat.name} groupchat!"))
        else:
            messages.info(request, _("You are already a member of this groupchat."))
    return redirect('groupchat_list')

@login_required
def leave_groupchat(request, pk):
    if request.method == 'POST':
        groupchat = get_object_or_404(GroupChat, pk=pk)
        if request.user in groupchat.members.all():
            groupchat.members.remove(request.user)
            messages.info(request, _(f"You have left the {groupchat.name} groupchat."))
        else:
            messages.error(request, _("You are not a member of this groupchat."))
    return redirect('groupchat_list')

@login_required
def add_g_comment(request, pk):
    groupchat = get_object_or_404(GroupChat, pk=pk)
    
    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            # We use the 'groupchat' object and 'request.user' to link the comment
            GComment.objects.create(
                groupchat=groupchat,
                user=request.user,
                text=content
            )
            messages.success(request, _("Comment added successfully."))
        else:
            messages.error(request, _("Comment cannot be empty."))
            
    return redirect('groupchat_detail', pk=pk)

def forgot_username(request):
    if request.method == "POST":
        email = request.POST.get('email')
        users = User.objects.filter(email=email)
        
        if users.exists():
            # In a real app, send an actual email for security
            usernames = [u.username for u in users]
            user_list = ", ".join(usernames)
            
            send_mail(
                _("Your JIBWIS Portal Username"),
                _("Hello, the username(s) associated with this email are: ") + user_list,
                "noreply@jibwis.org",
                [email],
                fail_silently=False,
            )
            messages.success(request, _("If an account exists with that email, we've sent the username."))
            return redirect('login')
        else:
            # We use the same message even if email doesn't exist for security (anti-enumeration)
            messages.success(request, _("If an account exists with that email, we've sent the username."))
            return redirect('login')
            
    return render(request, 'accounts/forgot_username.html')

@login_required
def edit_announcement(request, pk):
    # 1. Fetch the existing announcement or return 404
    announcement = get_object_or_404(Announcement, pk=pk)
    user_profile = request.user.profile

    # 2. Security Check: Only allow the author's unit or superuser to edit
    if not request.user.is_superuser and announcement.unit != user_profile.unit:
        messages.error(request, _("Access Denied: You can only edit announcements for your own unit."))
        return redirect('dashboard')

    if request.method == 'POST':
        # 3. Bind the POST data to the existing announcement instance
        form = AnnouncementForm(request.POST, instance=announcement)
        if form.is_valid():
            form.save()
            messages.success(request, _("Announcement updated successfully!"))
            return redirect('dashboard')
    else:
        # 4. GET request: Pre-fill the form with existing data
        form = AnnouncementForm(instance=announcement)

    return render(request, 'edit_announcement.html', {
        'form': form,
        'announcement': announcement,
        'title': _('Edit Announcement')
    })