from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from .models import (
    User, Profile, OrganizationUnit, Message, 
    VideoPost, PayrollRecord, GalleryImage, 
    Announcement, NewsUpdate
)

# --- 1. Inline Configuration ---
# This allows you to edit the Profile directly on the User page
class ProfileInline(admin.StackedInline):
    model = Profile
    extra = 0
    max_num = 1  # Ensures a user doesn't accidentally get multiple profiles
    can_delete = True
    verbose_name_plural = 'Member / Leader Profile'

# --- 2. Model Admin Customizations ---

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """
    Custom User Admin that includes the Profile inline and 
    displays bank details which we added to the User model.
    """
    inlines = (ProfileInline,)
    list_display = ('username', 'email', 'phone_number', 'get_unit', 'get_status', 'is_staff')
    list_filter = ('is_staff', 'is_superuser', 'profiles__is_active', 'profiles__unit__category')
    search_fields = ('username', 'email', 'phone_number')
    
    # Adding our custom fields to the User edit page
    fieldsets = UserAdmin.fieldsets + (
        ('Bank & Payment Information', {
            'fields': ('phone_number', 'bank_code', 'account_number', 'account_name', 'paystack_recipient_code')
        }),
        ('Additional Data', {
            'fields': ('education',)
        }),
    )

    def get_unit(self, obj):
        profile = obj.profiles.first()
        return profile.unit.name if profile else "No Profile"
    get_unit.short_description = 'Organization Unit'

    def get_status(self, obj):
        profile = obj.profiles.first()
        if profile:
            if profile.is_active:
                return format_html('<span style="color: green;">✅ Active</span>')
            return format_html('<span style="color: orange;">⏳ Pending</span>')
        return "❌ No Profile"
    get_status.short_description = 'Status'

@admin.register(OrganizationUnit)
class OrganizationUnitAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'level', 'parent')
    list_filter = ('category', 'level')
    search_fields = ('name',)  # REQUIRED for autocomplete_fields to work on 'parent'
    autocomplete_fields = ['parent']

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'unit', 'position', 'is_active')
    list_filter = ('is_active', 'unit__category', 'unit__level')
    search_fields = ('user__username', 'position', 'unit__name')
    autocomplete_fields = ['user', 'unit']
    actions = ['approve_profiles', 'deactivate_profiles']

    def approve_profiles(self, request, queryset):
        queryset.update(is_active=True)
    approve_profiles.short_description = "✅ Approve selected profiles"

    def deactivate_profiles(self, request, queryset):
        queryset.update(is_active=False)
    deactivate_profiles.short_description = "🚫 Deactivate selected profiles"

@admin.register(PayrollRecord)
class PayrollAdmin(admin.ModelAdmin):
    list_display = ('member', 'amount', 'month', 'year', 'status', 'payment_date')
    list_filter = ('status', 'month', 'year', 'payment_date')
    search_fields = ('member__username', 'reference')
    readonly_fields = ('payment_date', 'reference') # Prevent accidental tampering

@admin.register(NewsUpdate)
class NewsUpdateAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_pinned', 'created_at')
    list_editable = ('is_pinned',)
    search_fields = ('title',)

@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('content', 'is_active', 'created_at')
    list_editable = ('is_active',)

@admin.register(VideoPost)
class VideoAdmin(admin.ModelAdmin):
    list_display = ('title', 'views_count', 'created_at')
    search_fields = ('title',)

@admin.register(GalleryImage)
class GalleryAdmin(admin.ModelAdmin):
    list_display = ('title', 'order', 'created_at')
    list_editable = ('order',)

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'recipient', 'subject', 'timestamp')
    search_fields = ('subject', 'body', 'sender__username', 'recipient__username')