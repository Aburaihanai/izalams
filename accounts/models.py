from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings

# --- 1. Geographic Hierarchy Models ---

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

class Profile(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='profiles')
    unit = models.ForeignKey(OrganizationUnit, on_delete=models.CASCADE)
    position = models.CharField(max_length=100)
    profile_picture = models.ImageField(upload_to='profiles/', null=True, blank=True)
    education_level = models.CharField(max_length=100, blank=True, null=True)
    course_of_study = models.CharField(max_length=255, blank=True, null=True)
    graduation_year = models.IntegerField(blank=True, null=True)
    is_active = models.BooleanField(default=False) # Approval Switch

# --- 4. Messaging & Content ---

class Message(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_msgs')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_msgs')
    subject = models.CharField(max_length=255)
    body = models.TextField()
    is_read = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    recipient_deleted = models.BooleanField(default=False)
    sender_deleted = models.BooleanField(default=False)

class VideoPost(models.Model):
    title = models.CharField(max_length=200)
    video_file = models.FileField(upload_to='videos/')
    thumbnail = models.ImageField(upload_to='thumbnails/', blank=True)
    likes = models.ManyToManyField(User, related_name='video_likes', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    views_count = models.PositiveIntegerField(default=0)

    def __str__(self): return self.title

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
    content = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    unit = models.ForeignKey(OrganizationUnit, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Disbursement(models.Model):
    authorized_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='authorizations')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='SUCCESS')

class GalleryImage(models.Model):
    title = models.CharField(max_length=100, blank=True)
    image = models.ImageField(upload_to='gallery/')
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