from django.contrib import admin
from .models import CustomUser, Project, LecturerProfile, StudentProfile, ProjectSuggestion

# This allows you to edit these in the Admin panel
admin.site.register(CustomUser)
admin.site.register(Project)
admin.site.register(LecturerProfile)
admin.site.register(StudentProfile)
admin.site.register(ProjectSuggestion)