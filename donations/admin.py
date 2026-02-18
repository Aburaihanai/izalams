from django.contrib import admin
from .models import Donation, PaymentGateway

@admin.register(Donation)
class DonationAdmin(admin.ModelAdmin):
    list_display = ['reference', 'donor_name', 'amount', 'payment_method', 'status', 'created_at']
    list_filter = ['status', 'payment_method', 'created_at']
    search_fields = ['donor_name', 'donor_email', 'reference']
    readonly_fields = ['created_at', 'updated_at']
    actions = ['mark_as_completed']
    
    def mark_as_completed(self, request, queryset):
        queryset.update(status='completed')
    mark_as_completed.short_description = "Mark selected donations as completed"

@admin.register(PaymentGateway)
class PaymentGatewayAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active']
    list_editable = ['is_active']
    
"""from django.contrib import admin
from django.db.models import Sum, Count
from django.utils.html import format_html
from django.urls import path
from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta

# Import from donations.models, not accounts.models
from donations.models import Donation, DonationSetting, PaymentGateway, USSDProvider, USSDTransaction

@admin.register(Donation)
class DonationAdmin(admin.ModelAdmin):
    list_display = (
        'donor_name',
        'amount_display',
        'currency',
        'payment_method_display',
        'status_display',
        'purpose',
        'created_at_formatted'
    )
    list_filter = ('status', 'payment_method', 'created_at', 'currency', 'purpose')
    search_fields = ('donor_name', 'donor_email', 'donor_phone', 'transaction_id', 'purpose')
    readonly_fields = ('created_at', 'updated_at', 'transaction_id', 'payment_gateway_reference')
    date_hierarchy = 'created_at'
    list_per_page = 25
    
    fieldsets = (
        ('Donor Information', {
            'fields': ('donor_name', 'donor_email', 'donor_phone')
        }),
        ('Donation Details', {
            'fields': ('amount', 'currency', 'purpose', 'notes')
        }),
        ('Payment Information', {
            'fields': ('payment_method', 'status', 'transaction_id', 'payment_gateway_reference')
        }),
        ('USSD Information', {
            'fields': ('ussd_code', 'ussd_reference', 'ussd_provider'),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def amount_display(self, obj):
        return f"{obj.amount} {obj.currency}"
    amount_display.short_description = 'Amount'
    
    def payment_method_display(self, obj):
        return obj.get_payment_method_display()
    payment_method_display.short_description = 'Payment Method'
    
    def status_display(self, obj):
        color_map = {
            'completed': 'green',
            'pending': 'orange',
            'failed': 'red',
            'cancelled': 'gray'
        }
        color = color_map.get(obj.status, 'black')
        return format_html('<span style="color: {};">{}</span>', color, obj.get_status_display())
    status_display.short_description = 'Status'
    
    def created_at_formatted(self, obj):
        return obj.created_at.strftime("%Y-%m-%d %H:%M")
    created_at_formatted.short_description = 'Created At'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(created_by=request.user)
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('analytics/', self.admin_site.admin_view(self.analytics_view), name='donation_analytics'),
        ]
        return custom_urls + urls
    
    def analytics_view(self, request):
        total_donations = Donation.objects.aggregate(total=Sum('amount'))['total'] or 0
        completed_donations = Donation.objects.filter(status='completed').aggregate(total=Sum('amount'))['total'] or 0
        pending_donations = Donation.objects.filter(status='pending').aggregate(total=Sum('amount'))['total'] or 0
        
        donation_count = Donation.objects.count()
        completed_count = Donation.objects.filter(status='completed').count()
        
        payment_methods = Donation.objects.values('payment_method').annotate(
            total_amount=Sum('amount'),
            count=Count('id')
        ).order_by('-total_amount')
        
        statuses = Donation.objects.values('status').annotate(
            total_amount=Sum('amount'),
            count=Count('id')
        ).order_by('-total_amount')
        
        six_months_ago = timezone.now() - timedelta(days=180)
        monthly_trends = Donation.objects.filter(
            created_at__gte=six_months_ago
        ).extra(
            select={'month': "EXTRACT(month FROM created_at)", 'year': "EXTRACT(year FROM created_at)"}
        ).values('year', 'month').annotate(
            total_amount=Sum('amount'),
            count=Count('id')
        ).order_by('year', 'month')
        
        context = dict(
            self.admin_site.each_context(request),
            title='Donation Analytics',
            total_donations=total_donations,
            completed_donations=completed_donations,
            pending_donations=pending_donations,
            donation_count=donation_count,
            completed_count=completed_count,
            payment_methods=payment_methods,
            statuses=statuses,
            monthly_trends=monthly_trends,
        )
        
        return render(request, 'admin/donations/donation_analytics.html', context)

@admin.register(DonationSetting)
class DonationSettingAdmin(admin.ModelAdmin):
    list_display = ('key', 'value', 'description', 'updated_at')
    list_editable = ('value', 'description')
    readonly_fields = ('updated_at',)
    
    def value_preview(self, obj):
        if len(obj.value) > 50:
            return f"{obj.value[:50]}..."
        return obj.value
    value_preview.short_description = 'Value'

@admin.register(PaymentGateway)
class PaymentGatewayAdmin(admin.ModelAdmin):
    list_display = ('gateway_display', 'is_active', 'currency', 'minimum_amount', 'updated_at')
    list_editable = ('is_active', 'currency', 'minimum_amount')
    readonly_fields = ('created_at', 'updated_at')
    
    def gateway_display(self, obj):
        return obj.get_gateway_display()
    gateway_display.short_description = 'Gateway'
    
    fieldsets = (
        (None, {
            'fields': ('gateway', 'is_active')
        }),
        ('API Keys', {
            'fields': ('public_key', 'secret_key', 'webhook_secret'),
            'classes': ('collapse',)
        }),
        ('Configuration', {
            'fields': ('currency', 'minimum_amount')
        }),
        ('System Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(USSDProvider)
class USSDProviderAdmin(admin.ModelAdmin):
    list_display = ('provider_display', 'ussd_code', 'is_active', 'updated_at')
    list_editable = ('ussd_code', 'is_active')
    readonly_fields = ('created_at', 'updated_at')
    
    def provider_display(self, obj):
        return obj.get_provider_display()
    provider_display.short_description = 'Provider'

@admin.register(USSDTransaction)
class USSDTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'transaction_id_short', 
        'provider_display', 
        'amount_display', 
        'status_display', 
        'reference', 
        'created_at_formatted'
    )
    list_filter = ('status', 'provider', 'created_at')
    search_fields = ('transaction_id', 'reference', 'donation__donor_name')
    readonly_fields = ('transaction_id', 'created_at', 'updated_at', 'response_data_preview')
    
    def transaction_id_short(self, obj):
        return str(obj.transaction_id)[:8] + "..."
    transaction_id_short.short_description = 'Transaction ID'
    
    def provider_display(self, obj):
        return obj.get_provider_display()
    provider_display.short_description = 'Provider'
    
    def amount_display(self, obj):
        return f"₦{obj.amount}"
    amount_display.short_description = 'Amount'
    
    def status_display(self, obj):
        color_map = {
            'completed': 'green',
            'pending': 'orange',
            'failed': 'red',
            'cancelled': 'gray'
        }
        color = color_map.get(obj.status, 'black')
        return format_html('<span style="color: {};">{}</span>', color, obj.get_status_display())
    status_display.short_description = 'Status'
    
    def created_at_formatted(self, obj):
        return obj.created_at.strftime("%Y-%m-%d %H:%M")
    created_at_formatted.short_description = 'Created At'
    
    def response_data_preview(self, obj):
        if obj.response_data:
            return format_html('<pre>{}</pre>', str(obj.response_data))
        return "No response data"
    response_data_preview.short_description = 'Response Data'

# Proxy model for analytics
class DonationAnalytics(Donation):
    class Meta:
        proxy = True
        verbose_name = "Donation Analytics"
        verbose_name_plural = "Donation Analytics"

class DonationAnalyticsAdmin(admin.ModelAdmin):
    change_list_template = 'admin/donations/donation_analytics.html'
    
    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context=extra_context)
        
        if not hasattr(response, 'context_data'):
            return response
            
        total_donations = Donation.objects.aggregate(total=Sum('amount'))['total'] or 0
        completed_donations = Donation.objects.filter(status='completed').aggregate(total=Sum('amount'))['total'] or 0
        
        donation_count = Donation.objects.count()
        completed_count = Donation.objects.filter(status='completed').count()
        
        payment_methods = Donation.objects.values('payment_method').annotate(
            total_amount=Sum('amount'),
            count=Count('id')
        ).order_by('-total_amount')
        
        statuses = Donation.objects.values('status').annotate(
            total_amount=Sum('amount'),
            count=Count('id')
        ).order_by('-total_amount')
        
        response.context_data['analytics'] = {
            'total_donations': total_donations,
            'completed_donations': completed_donations,
            'donation_count': donation_count,
            'completed_count': completed_count,
            'payment_methods': payment_methods,
            'statuses': statuses,
        }
        
        return response

admin.site.register(DonationAnalytics, DonationAnalyticsAdmin)"""