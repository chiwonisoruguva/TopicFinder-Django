from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Project, LecturerProfile, StudentProfile, ProjectSuggestion

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ['email', 'username', 'role', 'is_verified', 'is_active']
    fieldsets = UserAdmin.fieldsets + (
        ('TopicFinder Fields', {
            'fields': ('role', 'is_verified', 'verification_code', 
                      'verification_code_expires', 'search_count')
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('TopicFinder Fields', {
            'fields': ('role', 'is_verified')
        }),
    )

admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Project)
admin.site.register(LecturerProfile)
admin.site.register(StudentProfile)
admin.site.register(ProjectSuggestion)