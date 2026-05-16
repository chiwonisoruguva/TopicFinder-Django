from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.utils import timezone
from django.db.models import Q
from django.http import JsonResponse
from datetime import timedelta
import random
from .models import (
    CustomUser, Project, ProjectTaken, ProjectFlag,
    StudentProfile, LecturerProfile, ProjectSuggestion, Tag
)


# ─────────────────────────────────────────
#  REGISTER
# ─────────────────────────────────────────

def register_view(request):
    if request.method == 'POST':
        name     = request.POST.get('name')
        email    = request.POST.get('email')
        password = request.POST.get('password')

        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, 'Email is already registered.')
            return redirect('register')

        code    = str(random.randint(1000, 9999))
        expires = timezone.now() + timedelta(minutes=10)

        user = CustomUser.objects.create_user(
            username=email, email=email, password=password,
            first_name=name, verification_code=code,
            verification_code_expires=expires, is_verified=False,
        )

        # Auto-create StudentProfile for new student accounts
       
        profile = StudentProfile(
            user=user,
            reg_number=f"REG{user.id:04d}",
            programme="Bachelor of Science in Computer Science",
            year_of_study=1,
        )
        profile.graduation_year = timezone.now().year + 4
        profile.save()

        try:
            send_mail(
                'Your TopicFinder Verification Code',
                f'Hi {name},\n\nYour verification code is: {code}\n\nThis code expires in 10 minutes.',
                None,
                [email],
                fail_silently=False,
            )
        except Exception as e:
            # Log the error but don't crash — user is still created
            print(f"Email sending failed: {e}")

        messages.success(request, 'Registration successful! Check your email for the verification code.')
        return redirect(f'/accounts/verify/?email={email}')

    return render(request, 'accounts/register.html')


# ─────────────────────────────────────────
#  VERIFY
# ─────────────────────────────────────────

def verify_view(request):
    email = request.GET.get('email', '') or request.POST.get('email', '')

    if request.method == 'POST':
        code = request.POST.get('code')
        try:
            user = CustomUser.objects.get(email=email)

            if user.is_verified:
                messages.error(request, 'Email is already verified.')
                return redirect('login')
            if user.verification_code != code:
                messages.error(request, 'Invalid verification code.')
                return render(request, 'accounts/verify.html', {'email': email})
            if user.verification_code_expires < timezone.now():
                messages.error(request, 'Verification code has expired.')
                return render(request, 'accounts/verify.html', {'email': email})

            user.is_verified = True
            user.verification_code = None
            user.verification_code_expires = None
            user.save()

            messages.success(request, 'Email verified! You can now log in.')
            return redirect('login')

        except CustomUser.DoesNotExist:
            messages.error(request, 'User not found.')
            return redirect('register')

    return render(request, 'accounts/verify.html', {'email': email})


# ─────────────────────────────────────────
#  LOGIN
# ─────────────────────────────────────────

def login_view(request):
    if request.method == 'POST':
        email         = request.POST.get('email')
        password      = request.POST.get('password')
        selected_role = request.POST.get('role', 'student').lower().strip()

        try:
            user = CustomUser.objects.get(email=email)

            if not user.is_verified:
                messages.error(request, 'Please verify your email before logging in.')
                return redirect('login')

            if user.role.lower() != selected_role:
                role_display = 'Lecturer' if user.role == 'lecturer' else 'Student'
                messages.error(request, f'This account is registered as a {role_display}. Please select the correct role.')
                return redirect('login')

            auth_user = authenticate(request, username=user.username, password=password)

            if auth_user is not None:
                login(request, auth_user)
                if auth_user.is_lecturer:
                    return redirect('lecturer_dashboard')
                return redirect('dashboard')
            else:
                messages.error(request, 'Invalid email or password.')
                return redirect('login')

        except CustomUser.DoesNotExist:
            messages.error(request, 'Invalid email or password.')
            return redirect('login')

    return render(request, 'accounts/login.html')


# ─────────────────────────────────────────
#  LOGOUT
# ─────────────────────────────────────────

def logout_view(request):
    logout(request)
    return redirect('login')


# ─────────────────────────────────────────
#  STUDENT DASHBOARD
# ─────────────────────────────────────────

def dashboard_view(request):
    if not request.user.is_authenticated:
        return redirect('login')
    if not request.user.is_verified:
        return redirect('login')
    if request.user.role == 'lecturer':
        return redirect('lecturer_dashboard')

    suggestions = ProjectSuggestion.objects.all().order_by('-created_at')[:5]

    return render(request, 'dashboard.html', {
        'user':        request.user,
        'suggestions': suggestions,
    })


# ─────────────────────────────────────────
#  DELETE ACCOUNT
# ─────────────────────────────────────────

def delete_account_view(request):
    if request.method == 'POST':
        user = request.user
        logout(request)
        user.delete()
        return render(request, 'accounts/goodbye.html')
    return redirect('dashboard')


# ─────────────────────────────────────────
#  LECTURER DASHBOARD
# ─────────────────────────────────────────

@login_required
def lecturer_dashboard_view(request):
    if not request.user.is_lecturer:
        return redirect('dashboard')

    profile     = get_object_or_404(LecturerProfile, user=request.user)
    projects    = Project.objects.filter(lecturer=profile).prefetch_related('tags').order_by('-created_at')
    suggestions = ProjectSuggestion.objects.filter(lecturer=profile).order_by('-created_at')
    tags        = Tag.objects.all().order_by('name')

    return render(request, 'accounts/lecturer_dashboard.html', {
        'user':        request.user,
        'profile':     profile,
        'projects':    projects,
        'suggestions': suggestions,
        'tags':        tags,
    })


# ─────────────────────────────────────────
#  ADD PROJECT
# ─────────────────────────────────────────

@login_required
def add_project_view(request):
    if not request.user.is_lecturer:
        return redirect('dashboard')

    if request.method == 'POST':
        profile = get_object_or_404(LecturerProfile, user=request.user)
        tag_ids = request.POST.getlist('tags')

        project = Project.objects.create(
            title           = request.POST.get('title'),
            description     = request.POST.get('description'),
            year            = request.POST.get('year'),
            status          = request.POST.get('status'),
            recommendations = request.POST.get('recommendations', ''),
            lecturer        = profile,
        )

        if tag_ids:
            project.tags.set(Tag.objects.filter(id__in=tag_ids))

        messages.success(request, 'Project added successfully!')

    return redirect('lecturer_dashboard')


# ─────────────────────────────────────────
#  ADD SUGGESTION
# ─────────────────────────────────────────

@login_required
def add_suggestion_view(request):
    if not request.user.is_lecturer:
        return redirect('dashboard')

    if request.method == 'POST':
        profile = get_object_or_404(LecturerProfile, user=request.user)

        ProjectSuggestion.objects.create(
            title       = request.POST.get('title'),
            description = request.POST.get('description'),
            lecturer    = profile,
        )
        messages.success(request, 'Suggestion posted successfully!')

    return redirect('lecturer_dashboard')


# ─────────────────────────────────────────
#  SUGGESTIONS (JSON for students)
# ─────────────────────────────────────────

@login_required
def suggestions_view(request):
    suggestions = ProjectSuggestion.objects.select_related('lecturer__user').order_by('-created_at')
    data = [{
        'id':          s.id,
        'title':       s.title,
        'description': s.description,
        'lecturer':    s.lecturer.user.get_full_name(),
        'department':  s.lecturer.department,
    } for s in suggestions]
    return JsonResponse({'suggestions': data, 'count': len(data)})


# ─────────────────────────────────────────
#  SEARCH (AJAX)
# ─────────────────────────────────────────

@login_required
def search_view(request):
    query = request.GET.get('q', '').strip().lower()

    SYNONYMS = {
        'ml':  'machine learning',
        'ai':  'artificial intelligence',
        'nlp': 'natural language processing',
        'dl':  'deep learning',
        'cv':  'computer vision',
        'db':  'database',
        'os':  'operating systems',
        'hci': 'human computer interaction',
        'iot': 'internet of things',
        'se':  'software engineering',
    }
    query = SYNONYMS.get(query, query)

    if not query:
        return JsonResponse({'error': 'Please enter a search term.'}, status=400)

    if request.user.search_count <= 0:
        return JsonResponse({'error': 'You have used all your search credits.'}, status=403)

    request.user.search_count -= 1
    request.user.save()

    projects = Project.objects.filter(
        Q(title__icontains=query) |
        Q(description__icontains=query) |
        Q(tags__name__icontains=query)
    ).distinct().prefetch_related('tags', 'taken').select_related('lecturer__user')

    taken_ids   = []
    flagged_ids = []
    if request.user.is_student:
        try:
            student     = request.user.student_profile
            taken_ids   = list(ProjectTaken.objects.values_list('project_id', flat=True))
            flagged_ids = list(ProjectFlag.objects.filter(student=student).values_list('project_id', flat=True))
        except StudentProfile.DoesNotExist:
            pass

    results = []
    for p in projects:
        lecturer_name = ''
        department    = ''
        if p.lecturer:
            lecturer_name = p.lecturer.user.get_full_name()
            department    = p.lecturer.department

        results.append({
            'id':              p.id,
            'title':           p.title,
            'description':     p.description,
            'year':            p.year,
            'status':          p.status,
            'recommendations': p.recommendations,
            'tags':            [t.name for t in p.tags.all()],
            'lecturer':        lecturer_name,
            'department':      department,
            'is_taken':        p.id in taken_ids,
            'is_flagged':      p.id in flagged_ids,
        })

    return JsonResponse({
        'results':           results,
        'count':             len(results),
        'credits_remaining': request.user.search_count,
        'query':             query,
    })


# ─────────────────────────────────────────
#  TAKE PROJECT (AJAX)
# ─────────────────────────────────────────

@login_required
def take_project_view(request, project_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method.'}, status=405)

    if not request.user.is_student:
        return JsonResponse({'error': 'Only students can take projects.'}, status=403)

    project = get_object_or_404(Project, id=project_id)

    if project.status != 'complete':
        return JsonResponse({'error': 'Only completed projects can be taken.'}, status=400)

    if hasattr(project, 'taken'):
        return JsonResponse({'error': 'This project has already been taken.'}, status=400)

    try:
        student_profile = request.user.student_profile
    except StudentProfile.DoesNotExist:
        return JsonResponse({'error': 'Student profile not found.'}, status=400)

    ProjectTaken.objects.create(project=project, student=student_profile)
    return JsonResponse({'success': True, 'message': f'You have successfully taken "{project.title}"!'})


# ─────────────────────────────────────────
#  FLAG PROJECT (AJAX)
# ─────────────────────────────────────────

@login_required
def flag_project_view(request, project_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method.'}, status=405)

    if not request.user.is_student:
        return JsonResponse({'error': 'Only students can flag projects.'}, status=403)

    project = get_object_or_404(Project, id=project_id)

    try:
        student_profile = request.user.student_profile
    except StudentProfile.DoesNotExist:
        return JsonResponse({'error': 'Student profile not found.'}, status=400)

    flag, created = ProjectFlag.objects.get_or_create(project=project, student=student_profile)

    if created:
        return JsonResponse({'success': True,  'message': 'Project flagged successfully.'})
    else:
        return JsonResponse({'success': False, 'message': 'You have already flagged this project.'})