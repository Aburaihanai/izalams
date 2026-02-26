from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.http import HttpResponse
import csv
from .models import (
    User, Profile, OrganizationUnit, Message,
    VideoPost, PayrollRecord, GalleryImage,
    Announcement, State, LGA, Ward
)


def export_to_csv(modeladmin, request, queryset):
    """
    Custom action to export selected members to a JIBWIS-standard CSV report.
    """
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="jibwis_member_report.csv"'
    writer = csv.writer(response)
    writer.writerow(['Username', 'Full Name', 'Email', 'Phone', 'Unit', 'Position', 'Education', 'Status'])

    for obj in queryset:
        profile = obj.profiles.first()
        unit_name = profile.unit.name if profile else "N/A"
        position = profile.position if profile else "N/A"
        status = "Active" if (profile and profile.is_active) else "Pending"

        writer.writerow([
            obj.username,
            obj.get_full_name(),
            obj.email,
            obj.phone_number,
            unit_name,
            position,
            obj.education_level,
            status
        ])
    return response

export_to_csv.short_description = "📊 Export Selected to JIBWIS CSV Report"

# --- 2. Inline Configuration ---

class ProfileInline(admin.StackedInline):
    model = Profile
    extra = 0
    max_num = 1
    can_delete = True
    verbose_name_plural = 'Member / Leader Profile'

# --- 3. Model Admin Customizations ---

@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(LGA)
class LGAAdmin(admin.ModelAdmin):
    list_display = ('name', 'state')
    list_filter = ('state',)
    search_fields = ('name',)

@admin.register(Ward)
class WardAdmin(admin.ModelAdmin):
    list_display = ('name', 'lga', 'get_state')
    list_filter = ('lga__state', 'lga')
    search_fields = ('name',)

    def get_state(self, obj):
        return obj.lga.state
    get_state.short_description = 'State'

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    inlines = (ProfileInline,)
    actions = [export_to_csv]
    list_display = ('username', 'get_full_name', 'phone_number', 'education_level', 'get_unit', 'get_status')
    list_filter = ('is_staff', 'education_level', 'profiles__is_active', 'profiles__unit__level')
    search_fields = ('username', 'first_name', 'last_name', 'phone_number')

    fieldsets = UserAdmin.fieldsets + (
        ('Bank & Payment Information', {
            'fields': ('phone_number', 'bank_code', 'account_number', 'account_name', 'paystack_recipient_code')
        }),
        ('Detailed Education Credentials', {
            'fields': ('education_level', 'course_of_study', 'is_graduated', 'graduation_year')
        }),
    )

    def get_unit(self, obj):
        profile = obj.profiles.first()
        return profile.unit.name if profile else "No Profile"
    get_unit.short_description = 'Unit'

    def get_status(self, obj):
        profile = obj.profiles.first()
        if profile:
            color = "green" if profile.is_active else "orange"
            text = "Active" if profile.is_active else "Pending"
            return format_html(f'<span style="color: {color}; fw-bold">● {text}</span>')
        return "No Profile"
    get_status.short_description = 'Status'

@admin.register(OrganizationUnit)
class OrganizationUnitAdmin(admin.ModelAdmin):
    list_display = ('name', 'level', 'category', 'ward_name', 'lga', 'state')
    list_filter = ('level', 'category', 'state', 'lga')
    search_fields = ('name', 'ward_name', 'lga__name', 'state__name')
    autocomplete_fields = ['lga', 'state']

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'unit', 'position', 'is_active')
    list_filter = ('is_active', 'unit__category', 'unit__level')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'unit__name')
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
    list_filter = ('status', 'month', 'year')
    search_fields = ('member__username', 'reference')
    readonly_fields = ('payment_date', 'reference')

@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('content', 'is_active', 'created_at')
    list_editable = ('is_active',)

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'recipient', 'subject', 'timestamp')
    readonly_fields = ('timestamp',)

admin.site.register(VideoPost)
admin.site.register(GalleryImage)