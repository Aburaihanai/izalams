from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from datetime import date
import uuid
from izalams import settings
from django.utils import timezone

class Donation(models.Model):
    PAYMENT_METHODS = (
        ('card', 'Card Payment'),
        ('transfer', 'Bank Transfer'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    )
    
    # Donor information
    donor_name = models.CharField(max_length=255)
    donor_email = models.EmailField(blank=True, null=True)
    donor_phone = models.CharField(max_length=20)
    
    # Donation details
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    purpose = models.CharField(max_length=255, default='Zakka')
    notes = models.TextField(blank=True, null=True)
    
    # Payment information
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reference = models.CharField(max_length=100, unique=True)
    
    # Card payment fields (if applicable)
    card_last_four = models.CharField(max_length=4, blank=True, null=True)
    card_type = models.CharField(max_length=50, blank=True, null=True)
    authorization_code = models.CharField(max_length=100, blank=True, null=True)
    
    # Bank transfer fields (if applicable)
    bank_name = models.CharField(max_length=255, blank=True, null=True)
    account_number = models.CharField(max_length=50, blank=True, null=True)
    transfer_reference = models.CharField(max_length=100, blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.donor_name} - ₦{self.amount} - {self.status}"
    
    def generate_reference(self):
        import uuid
        return f"DON-{uuid.uuid4().hex[:12].upper()}"
    
    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self.generate_reference()
        super().save(*args, **kwargs)
    
    def mark_completed(self):
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()

class PaymentGateway(models.Model):
    GATEWAY_CHOICES = (
        ('paystack', 'Paystack'),
        ('flutterwave', 'Flutterwave'),
        ('stripe', 'Stripe'),
    )
    
    name = models.CharField(max_length=50, choices=GATEWAY_CHOICES)
    is_active = models.BooleanField(default=True)
    public_key = models.CharField(max_length=255)
    secret_key = models.CharField(max_length=255)
    webhook_secret = models.CharField(max_length=255, blank=True, null=True)
    
    def __str__(self):
        return self.get_name_display()