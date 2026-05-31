from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


# ─────────────────────────────────────────
#  CUSTOM USER
# ─────────────────────────────────────────

class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('lecturer', 'Lecturer'),
    )

    role                     = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student')
    is_verified              = models.BooleanField(default=False)
    verification_code        = models.CharField(max_length=4, blank=True, null=True)
    verification_code_expires = models.DateTimeField(blank=True, null=True)
    search_count             = models.IntegerField(default=10)    
    search_credits_reset_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.email

    @property
    def is_lecturer(self):
        return self.role == 'lecturer'

    @property
    def is_student(self):
        return self.role == 'student'

    last_search_time = models.DateTimeField(default=timezone.now)

# ─────────────────────────────────────────
#  LECTURER PROFILE
# ─────────────────────────────────────────

class LecturerProfile(models.Model):
    user              = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='lecturer_profile')
    lecturer_id       = models.CharField(max_length=20, unique=True)   # unique assigned lecturer ID
    staff_number      = models.CharField(max_length=20, unique=True)   # employee/staff number
    department        = models.CharField(max_length=100)
    area_of_expertise = models.CharField(max_length=200)
    years_of_experience = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.user.get_full_name()} — {self.department}"


# ─────────────────────────────────────────
#  STUDENT PROFILE
# ─────────────────────────────────────────

class StudentProfile(models.Model):
    user            = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='student_profile')
    reg_number      = models.CharField(max_length=20, unique=True)     # student registration number
    programme       = models.CharField(max_length=150)                 # e.g. BSc Computer Science
    year_of_study   = models.PositiveIntegerField()                    # 1, 2, 3, or 4
    graduation_year = models.PositiveIntegerField(editable=False)      # auto-calculated: date_joined year + 4

    def save(self, *args, **kwargs):
        # Calculate graduation year from the year the user account was created
        if not self.graduation_year:
            self.graduation_year = self.user.date_joined.year + 4
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.get_full_name()} — {self.reg_number}"


# ─────────────────────────────────────────
#  TAGS  (predefined fixed list)
# ─────────────────────────────────────────

class Tag(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


# ─────────────────────────────────────────
#  PROJECT
# ─────────────────────────────────────────

class Project(models.Model):
    STATUS_CHOICES = (
        ('complete', 'Complete'),
        ('in_progress', 'In Progress'),
    )

    title           = models.CharField(max_length=255)
    description     = models.TextField()
    year            = models.PositiveIntegerField()                    # year the project was done
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES)
    recommendations = models.TextField()  
    category        = models.CharField(max_length=100)  # Make sure this line exists!                             # suggestions for future students
    lecturer        = models.ForeignKey(LecturerProfile, on_delete=models.SET_NULL, null=True, related_name='projects')
    tags            = models.ManyToManyField(Tag, related_name='projects')
    created_at      = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.title

    @property
    def is_taken(self):
        return hasattr(self, 'taken')   # True if a ProjectTaken record exists


# ─────────────────────────────────────────
#  PROJECT TAKEN
# ─────────────────────────────────────────

class ProjectTaken(models.Model):
    project   = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='taken')
    student   = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='taken_projects')
    taken_at  = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.project.title} — taken by {self.student.user.get_full_name()}"


# ─────────────────────────────────────────
#  PROJECT FLAGS
# ─────────────────────────────────────────

class ProjectFlag(models.Model):
    project    = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='flags')
    student    = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='flagged_projects')
    flagged_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('project', 'student')   # a student can only flag a project once

    def __str__(self):
        return f"{self.project.title} flagged by {self.student.user.get_full_name()}"


    # ─────────────────────────────────────────
#  PROJECT SUGGESTION (New)
# ─────────────────────────────────────────

class ProjectSuggestion(models.Model):
    title = models.CharField(max_length=255)
    brief_description = models.TextField()
    suggested_by = models.ForeignKey(LecturerProfile, on_delete=models.CASCADE, related_name='suggestions')
    created_at = models.DateTimeField(auto_now_add=True)

    def __clstr__(self):
        return self.title