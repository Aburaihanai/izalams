from django.contrib import admin
from .models import Announcement, GalleryImage, User, OrganizationUnit, Profile, VideoPost, PayrollRecord

@admin.register(OrganizationUnit)
class OrganizationUnitAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'level', 'parent')
    list_filter = ('category', 'level')
    search_fields = ('name',)
    # This helps you build the tree from National down to Ward
    autocomplete_fields = ['parent'] 

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'unit', 'position', 'is_active')
    list_filter = ('is_active', 'unit__category', 'unit__level')
    search_fields = ('user__username', 'position')
    actions = ['approve_profiles']

    def approve_profiles(self, request, queryset):
        queryset.update(is_active=True)
    approve_profiles.short_description = "Approve selected profiles"

@admin.register(VideoPost)
class VideoAdmin(admin.ModelAdmin):
    list_display = ('title', 'created_at')

@admin.register(PayrollRecord)
class PayrollAdmin(admin.ModelAdmin):
    list_display = ('member', 'amount', 'month', 'year', 'status', 'payment_date')
    list_filter = ('status', 'month', 'year')
    search_fields = ('member__username', 'reference')

@admin.register(GalleryImage)
class GalleryAdmin(admin.ModelAdmin):
    list_display = ('title', 'order', 'created_at')
    list_editable = ('order',)


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('content', 'is_active', 'created_at')
    list_editable = ('is_active',)
# Register the custom User model
admin.site.register(User)