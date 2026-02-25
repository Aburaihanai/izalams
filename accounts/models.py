from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    # Add these fields here so the Form can find them
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    education = models.CharField(max_length=255, blank=True, null=True)


    BANK_CHOICES = [
        ('044', 'Access Bank'),
        ('011', 'First Bank of Nigeria'),
        ('058', 'GTBank'),
        ('057', 'Zenith Bank'),
        ('033', 'United Bank for Africa (UBA)'),
        ('050', 'EcoBank'),
        ('070', 'Fidelity Bank'),
        ('030', 'Heritage Bank'),
        ('082', 'Keystone Bank'),
        ('076', 'Polaris Bank'),
        ('232', 'Sterling Bank'),
        ('032', 'Union Bank'),
        ('215', 'Unity Bank'),
        ('035', 'Wema Bank'),
        ('068', 'Standard Chartered'),
        ('214', 'First City Monument Bank (FCMB)'),
        ('50515', 'Moniepoint MFB'),
        ('999992', 'OPay'),
        ('999991', 'PalmPay'),
        ('50211', 'Kuda Bank'),
    ]

    bank_code = models.CharField(max_length=10, choices=BANK_CHOICES, blank=True, null=True)
    account_number = models.CharField(max_length=10, blank=True, null=True)
    account_name = models.CharField(max_length=100, blank=True, null=True, help_text="Verified name from Bank")
    paystack_recipient_code = models.CharField(max_length=100, blank=True, null=True)

    groups = models.ManyToManyField(
        'auth.Group',
        related_name='custom_user_groups',
        blank=True
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='custom_user_permissions',
        blank=True
    )

class OrganizationUnit(models.Model):
    CATEGORY_CHOICES = [('ADMIN', 'Administration'), ('ULAMA', 'Council of Ulama'), ('FAG', 'First Aid Group')]
    LEVEL_CHOICES = [('NATIONAL', 'National'), ('STATE', 'State'), ('LG', 'Local Government'), ('WARD', 'Ward/Unit')]
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES)
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='sub_units')
    def __str__(self): return f"{self.category} - {self.name}"

    @property
    def short_name(self):
        return "".join([word[0].upper() for word in self.name.split()])

class Profile(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='profiles')
    unit = models.ForeignKey(OrganizationUnit, on_delete=models.CASCADE)
    position = models.CharField(max_length=100)
    account_number = models.CharField(max_length=10, null=True, blank=True)
    bank_name = models.CharField(max_length=100, null=True, blank=True)
    bank_code = models.CharField(max_length=3, null=True, blank=True)
    is_active = models.BooleanField(default=False)

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

    def total_likes(self):
        return self.likes.count()

    def __str__(self):
        return self.title

# accounts/models.py
class PayrollRecord(models.Model):
    member = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateTimeField(auto_now_add=True)
    month = models.CharField(max_length=20, blank=True, null=True)
    year = models.IntegerField(blank=True, null=True)
    status = models.CharField(max_length=20, default='pending')
    reference = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

class GalleryImage(models.Model):
    title = models.CharField(max_length=100, blank=True)
    image = models.ImageField(upload_to='gallery/')
    order = models.IntegerField(default=0) # To control which image shows first
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title or f"Gallery Image {self.id}"

class Announcement(models.Model):
    content = models.CharField(max_length=255) # The scrolling text
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    unit = models.ForeignKey('OrganizationUnit', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return self.content[:50]

class NewsUpdate(models.Model):
    title = models.CharField(max_length=200)
    image = models.ImageField(upload_to='news/')
    tiktok_url = models.URLField(blank=True, help_text="Paste TikTok video link here")
    created_at = models.DateTimeField(auto_now_add=True)
    is_pinned = models.BooleanField(default=False)

    class Meta:
        ordering = ['-is_pinned', '-created_at']

    def __str__(self):
        return self.title

class DisciplinaryReport(models.Model):
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reports_made")
    subject_leader = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reports_against")
    complaint = models.TextField()
    evidence = models.FileField(upload_to='reports/', null=True, blank=True)
    status = models.CharField(max_length=20, default='pending') # pending, investigating, resolved
    created_at = models.DateTimeField(auto_now_add=True)

class Disbursement(models.Model):
    authorized_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='authorizations')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='SUCCESS')

    def __str__(self):
        return f"{self.recipient.username} - {self.amount}"