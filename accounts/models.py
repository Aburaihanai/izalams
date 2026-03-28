from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.contrib.auth.models import User
import os
from django.db import models
from django.core.files.base import ContentFile
from moviepy.video.io.VideoFileClip import VideoFileClip
from io import BytesIO
from PIL import Image
from django.contrib.auth import get_user_model

User = settings.AUTH_USER_MODEL

CATEGORY_CHOICES = [
    ('ADMIN', 'Administration'), 
    ('ULAMA', 'Council of Ulama'), 
    ('FAG', 'First Aid Group'),
]

class State(models.Model):
    name = models.CharField(max_length=50, unique=True)
    def __str__(self): return self.name

class LGA(models.Model):
    state = models.ForeignKey(State, on_delete=models.CASCADE, related_name='lgas')
    name = models.CharField(max_length=50)
    def __str__(self): return f"{self.name} ({self.state.name})"

class Ward(models.Model):
    lga = models.ForeignKey(LGA, on_delete=models.CASCADE, related_name='wards')
    name = models.CharField(max_length=50)
    def __str__(self): return f"{self.name} - {self.lga.name}"

# --- 2. Custom User Model ---

class User(AbstractUser):
    phone_number = models.CharField(max_length=15, blank=True, null=True)

    # Financial Information
    BANK_CHOICES = [
        ('044', 'Access Bank'), ('011', 'First Bank'), ('058', 'GTBank'),
        ('057', 'Zenith Bank'), ('033', 'UBA'), ('050', 'EcoBank'),
        ('50515', 'Moniepoint MFB'), ('999992', 'OPay'), ('999991', 'PalmPay'),
    ]
    bank_code = models.CharField(max_length=10, choices=BANK_CHOICES, blank=True, null=True)
    account_number = models.CharField(max_length=10, blank=True, null=True)
    account_name = models.CharField(max_length=100, blank=True, null=True, help_text="Verified name from Bank")
    paystack_recipient_code = models.CharField(max_length=100, blank=True, null=True)

    # Detailed Education
    EDUCATION_LEVELS = [
        ('primary', 'Primary'), ('secondary', 'Secondary/SSCE'),
        ('tertiary', 'College/NCE'), ('polytechnics', 'Certificate/ND'),
        ('undergraduate', 'Undergraduate'), ('graduate', 'Graduate (BSc/HND)'),
        ('postgraduate', 'Postgraduate (MSc/PhD)'), ('specialized', 'Specialized/Technical'),
    ]
    education_level = models.CharField(max_length=20, choices=EDUCATION_LEVELS, blank=True)
    course_of_study = models.CharField(max_length=255, blank=True)
    is_graduated = models.BooleanField(default=False)
    graduation_year = models.PositiveIntegerField(null=True, blank=True)

    groups = models.ManyToManyField('auth.Group', related_name='custom_user_groups', blank=True)
    user_permissions = models.ManyToManyField('auth.Permission', related_name='custom_user_permissions', blank=True)

# --- 3. Organizational Models ---

class OrganizationUnit(models.Model):
    CATEGORY_CHOICES = [('ADMIN', 'Administration'), ('ULAMA', 'Council of Ulama'), ('FAG', 'First Aid Group')]
    LEVEL_CHOICES = [('NATIONAL', 'National'), ('STATE', 'State'), ('LG', 'Local Government'), ('WARD', 'Ward/Unit')]

    name = models.CharField(max_length=100)
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES)
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES)

    # NEW: Linking the Unit to a physical location
    state = models.ForeignKey(State, on_delete=models.SET_NULL, null=True, blank=True)
    lga = models.ForeignKey(LGA, on_delete=models.SET_NULL, null=True, blank=True)
    ward_name = models.CharField(max_length=255, null=True, blank=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='sub_units')

    def __str__(self): return f"{self.get_category_display()} - {self.name}"
    
    class Meta:
        # This ensures you can't have two "National FAG" units
        unique_together = ('category', 'level', 'state', 'lga', 'name')

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    unit = models.ForeignKey(OrganizationUnit, on_delete=models.CASCADE)
    position = models.CharField(max_length=100)
    profile_picture = models.ImageField(upload_to='profiles/', null=True, blank=True)
    education_level = models.CharField(max_length=100, blank=True, null=True)
    course_of_study = models.CharField(max_length=255, blank=True, null=True)
    graduation_year = models.IntegerField(blank=True, null=True)
    is_active = models.BooleanField(default=False)
    is_leader = models.BooleanField(default=False)

class UnitBroadcast(models.Model):
    MESSAGE_TYPES = (
        ('TEXT', 'Text/File Broadcast'),
        ('VOICE', 'Voice Directive'),
    )
    
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_broadcasts')
    recipients = models.ManyToManyField(User, related_name='received_broadcasts')
    subject = models.CharField(max_length=255, blank=True, null=True)
    body = models.TextField(blank=True, null=True)
    
    # File & Voice Storage
    attachment = models.FileField(upload_to='broadcasts/attachments/', blank=True, null=True)
    voice_recording = models.FileField(upload_to='broadcasts/voice/', blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES)

    def __str__(self):
        return f"From {self.sender.username} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"

# --- 4. Messaging & Content ---
class Message(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_msgs')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_msgs')
    subject = models.CharField(max_length=255, blank=True, null=True)
    body = models.TextField(blank=True, null=True)
    attachment = models.FileField(
        upload_to='messages/attachments/%Y/%m/', 
        blank=True, 
        null=True
    )
    voice_note = models.FileField(
        upload_to='messages/voice_notes/%Y/%m/', 
        blank=True, 
        null=True
    )
    
    # Status & Logistics
    is_read = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Soft Delete for Isolation (WhatsApp 'Delete for Me' logic)
    recipient_deleted = models.BooleanField(default=False)
    sender_deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ['-timestamp'] # Newest messages first

    def __str__(self):
        return f"From {self.sender} to {self.recipient} at {self.timestamp}"

class UnitChat(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    recipients = models.ManyToManyField(User, related_name='received_chats')
    
    # Content types
    text_content = models.TextField(blank=True, null=True)
    file_attachment = models.FileField(upload_to='chats/files/', blank=True, null=True)
    voice_note = models.FileField(upload_to='chats/voice/', blank=True, null=True)
    
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

class VideoPost(models.Model):
    title = models.CharField(max_length=200)
    video_file = models.FileField(upload_to='videos/')
    thumbnail = models.ImageField(upload_to='thumbnails/', null=True, blank=True)
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES, default='ADMIN')
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Corrected spelling from 'discription' to 'description'
    description = models.TextField(blank=True, null=True) 
    
    # Added creator field to link the video to the staff member
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='uploaded_videos',
        null=True,
        blank=True
    )

    def save(self, *args, **kwargs):
        # 1. Save the video first to get a file path
        super().save(*args, **kwargs)

        # 2. Generate thumbnail if video exists and thumbnail doesn't
        if self.video_file and not self.thumbnail:
            try:
                video_path = self.video_file.path
                # Ensure MoviePy can handle the file
                clip = VideoFileClip(video_path)
                
                # Get frame at 1 second
                frame = clip.get_frame(1) 
                
                img = Image.fromarray(frame)
                temp_thumb = BytesIO()
                img.save(temp_thumb, format='JPEG')
                temp_thumb.seek(0)

                thumb_name = os.path.basename(video_path).rsplit('.', 1)[0] + '_thumb.jpg'
                self.thumbnail.save(thumb_name, ContentFile(temp_thumb.read()), save=False)
                
                clip.close()
                
                # Use update_fields to save ONLY the thumbnail and avoid recursion
                super().save(update_fields=['thumbnail'])
            except Exception as e:
                print(f"Error generating thumbnail: {e}")
# --- 5. Financial & Admin Tools ---

class PayrollRecord(models.Model):
    member = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    month = models.CharField(max_length=20, blank=True, null=True)
    year = models.IntegerField(blank=True, null=True)
    status = models.CharField(max_length=20, default='pending')
    reference = models.CharField(max_length=100, unique=True)
    payment_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Announcement(models.Model):
    # Changed to TextField for longer messages
    content = models.TextField() 
    is_active = models.BooleanField(default=True)
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES, default='ADMIN')
    unit = models.ForeignKey('OrganizationUnit', on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.category} - {self.created_at.strftime('%Y-%m-%d')}"

class Disbursement(models.Model):
    authorized_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='authorizations')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='SUCCESS')

class GalleryImage(models.Model):
    title = models.CharField(max_length=100, blank=True)
    image = models.ImageField(upload_to='gallery/')
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES, default='ADMIN')
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title or f"Gallery Image {self.id}"

class DisciplinaryReport(models.Model):
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reports_made")
    subject_leader = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reports_against")
    complaint = models.TextField()
    evidence = models.FileField(upload_to='reports/', null=True, blank=True)
    status = models.CharField(max_length=20, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

class GroupChat(models.Model):
    LEVEL_CHOICES = [
        ('NATIONAL', 'National'),
        ('STATE', 'State'),
        ('LGA', 'LGA'),
        ('WARD', 'Ward'),
    ]

    name = models.CharField(max_length=255) # e.g., "Zakkah Distribution groupchat"
    description = models.TextField(blank=True, null=True)
    
    # The Unit this groupchat belongs to (e.g., Kaduna North LGA)
    unit = models.ForeignKey(OrganizationUnit, on_delete=models.CASCADE, related_name='groupchats')
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES)

    # The person who created the group (The Chairman)
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_groupchats')

    # The appointed "WhatsApp-style" Admin/Leader of this specific group
    team_lead = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='led_groupchats')

    # The list of all people in the group
    members = models.ManyToManyField(User, related_name='groupchat_memberships', blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.get_level_display()})"


class Committee(models.Model):
    LEVEL_CHOICES = [
        ('NATIONAL', 'National'),
        ('STATE', 'State'),
        ('LGA', 'LGA'),
        ('WARD', 'Ward'),
    ]

    name = models.CharField(max_length=255) # e.g., "Zakkah Distribution Committee"
    description = models.TextField(blank=True, null=True)
    
    # The Unit this committee belongs to (e.g., Kaduna North LGA)
    unit = models.ForeignKey(OrganizationUnit, on_delete=models.CASCADE, related_name='committees')
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES)

    # The person who created the group (The Chairman)
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_committees')

    # The appointed "WhatsApp-style" Admin/Leader of this specific group
    team_lead = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='led_committees')

    # The list of all people in the group
    members = models.ManyToManyField(User, related_name='committee_memberships', blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.get_level_display()})"



class CommitteeReport(models.Model):
    committee = models.ForeignKey(Committee, on_delete=models.CASCADE, related_name='reports')
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='committee_reports/%Y/%m/')
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.committee.name}"

class Comment(models.Model):
    committee = models.ForeignKey(
        'Committee', 
        on_delete=models.CASCADE, 
        related_name='comments'
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Helpful for JIBWIS to distinguish between a member's question 
    # and a Leader's official directive.
    is_official = models.BooleanField(default=False)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Comment by {self.user.username} on {self.committee.name}"

class GComment(models.Model):
    groupchat = models.ForeignKey('GroupChat', on_delete=models.CASCADE, related_name='g_comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Helpful for JIBWIS to distinguish between a member's question 
    # and a Leader's official directive.
    is_official = models.BooleanField(default=False)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"GComment by {self.user.username} on {self.groupchat.name}"

class Masjid(models.Model):
    MASJID_TYPES = (
        ('FIVE', 'Five Daily Prayer'), ("JUMU'AH", 'Friday Congrigational Prayer'),
    )
    name = models.CharField(max_length=255)
    masjid_types = models.CharField(max_length=20, choices=MASJID_TYPES)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    address = models.CharField(max_length=2500, blank=True, null=True)
    unit = models.ForeignKey('OrganizationUnit', on_delete=models.CASCADE, related_name='unit_masjids')
    imam = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='managed_masjids')
    capacity = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.get_masjid_types_display()})"

# --- SCHOOLS ---
class School(models.Model):
    SCHOOL_TYPES = (
        ('NURSERY', 'Nursery'), ('PRIMARY', 'Primary'), ('SECONDARY', 'Secondary'),
        ('ISLAMIYYA', 'Islamiyya'), ('QURANIC', 'Quranic'), ('TERTIARY', 'Tertiary'),
    )
    name = models.CharField(max_length=255)
    school_type = models.CharField(max_length=20, choices=SCHOOL_TYPES)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    unit = models.ForeignKey('OrganizationUnit', on_delete=models.CASCADE, related_name='unit_schools')
    head = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='managed_schools')
    total_male_students = models.PositiveIntegerField(default=0)
    total_female_students = models.PositiveIntegerField(default=0)
    total_teachers = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    def total_students(self):
        return self.total_male_students + self.total_female_students

    def __str__(self):
        return f"{self.name} ({self.get_school_type_display()})"
    
class SchoolMembership(models.Model):
    MEMBERSHIP_TYPES = [
        ('student', 'Student'),
        ('teacher', 'Teacher'),
        ('staff', 'Staff'),
    ]

    member = models.ForeignKey(User, on_delete=models.CASCADE, related_name='school_memberships')
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='members')
    membership_type = models.CharField(max_length=20, choices=MEMBERSHIP_TYPES, default='regular')
    join_date = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('member', 'school')

    def __str__(self):
        return f"{self.member.username} - {self.school.name}"

# --- HOSPITALS ---

class Hospital(models.Model):
    name = models.CharField(max_length=255)
    unit = models.ForeignKey(OrganizationUnit, on_delete=models.CASCADE, related_name='unit_hospitals', null=True, blank=True)
    medical_director = models.CharField(max_length=255)
    num_staff = models.PositiveIntegerField(default=0)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class HospitalMembership(models.Model):
    MEMBERSHIP_TYPES = [
        ('patient', 'Patient'),
        ('doctor', 'Doctor'),
        ('staff', 'Staff'),
    ]
    
    member = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hospital_memberships')
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name='members')
    membership_type = models.CharField(max_length=20, choices=MEMBERSHIP_TYPES, default='regular')
    join_date = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ('member', 'hospital')
    
    def __str__(self):
        return f"{self.member.username} - {self.hospital.name}"