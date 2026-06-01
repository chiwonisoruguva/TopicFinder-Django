from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Q
from django.http import JsonResponse
from datetime import timedelta
import random
import os
import json
import urllib.request
from .models import (
    CustomUser, Project, ProjectTaken, ProjectFlag,
    StudentProfile, LecturerProfile, ProjectSuggestion, Tag
)


# ─────────────────────────────────────────
#  SEND EMAIL via SendGrid Web API
#  (bypasses SMTP port blocking on Railway)
# ─────────────────────────────────────────

def send_verification_email(to_email, name, code):
    api_key = os.environ.get('SENDGRID_API_KEY', '')
    if not api_key:
        print("ERROR: SENDGRID_API_KEY not set")
        return False

    data = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": "mamoruguva@gmail.com", "name": "TopicFinder"},
        "subject": "Your TopicFinder Verification Code",
        "content": [{
            "type": "text/plain",
            "value": f"Hi {name},\n\nYour TopicFinder verification code is: {code}\n\nThis code expires in 10 minutes.\n\nIf you did not register, ignore this email."
        }]
    }

    req = urllib.request.Request(
        'https://api.sendgrid.com/v3/mail/send',
        data=json.dumps(data).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        },
        method='POST'
    )

    try:
        response = urllib.request.urlopen(req)
        print(f"EMAIL SENT to {to_email} — status {response.status}")
        return True
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8')
        print(f"EMAIL HTTP ERROR {e.code}: {body}")
        return False
    except Exception as e:
        print(f"EMAIL ERROR: {str(e)}")
        return False


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

        try:
            code    = str(random.randint(1000, 9999))
            expires = timezone.now() + timedelta(minutes=10)

            user = CustomUser.objects.create_user(
                username=email, email=email, password=password,
                first_name=name, verification_code=code,
                verification_code_expires=expires, is_verified=False,
            )
            print(f"USER CREATED: {user.email} id={user.id}")

            sent = send_verification_email(email, name, code)
            if sent:
                print(f"Verification email sent to {email}")
            else:
                print(f"Verification email FAILED for {email}")

            messages.success(request, 'Registration successful! Check your email for the verification code.')
            return redirect(f'/accounts/verify/?email={email}')

        except Exception as e:
            print(f"REGISTER ERROR: {str(e)}")
            messages.error(request, 'Registration failed. Please try again.')
            return redirect('register')

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

            auth_user = authenticate(request, username=user.email, password=password)

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

    # Reset credits if 5 minutes have passed
    user = request.user
    if user.search_credits_reset_at:
        elapsed = timezone.now() - user.search_credits_reset_at
        if elapsed >= timedelta(minutes=5):
            user.search_count = 10
            user.search_credits_reset_at = None
            user.save()

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
    suggestions = ProjectSuggestion.objects.filter(suggested_by=profile).order_by('-created_at')
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
            title             = request.POST.get('title'),
            brief_description = request.POST.get('brief_description'),  # model uses brief_description
            suggested_by      = profile,                          # model uses suggested_by
        )
        messages.success(request, 'Suggestion posted successfully!')

    return redirect('lecturer_dashboard')


# ─────────────────────────────────────────
#  SUGGESTIONS (JSON for students)
# ─────────────────────────────────────────
@login_required
def suggestions_page_view(request):
    suggestions = ProjectSuggestion.objects.select_related(
        'suggested_by__user'
    ).order_by('-created_at')
    return render(request, 'accounts/suggestions_list.html', {
        'suggestions': suggestions,
        'user': request.user,
    })

@login_required
def suggestions_view(request):
    suggestions = ProjectSuggestion.objects.select_related('suggested_by__user').order_by('-created_at')
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
    user = request.user

    # Reset credits if 5 minutes have passed
    if user.search_credits_reset_at:
        elapsed = timezone.now() - user.search_credits_reset_at
        if elapsed >= timedelta(minutes=5):
            user.search_count = 10
            user.search_credits_reset_at = None
            user.save()

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

    if user.search_count <= 0:
        return JsonResponse({'error': 'You have used all your search credits.'}, status=403)

    user.search_count -= 1
    if user.search_count == 0:
        user.search_credits_reset_at = timezone.now()  # Start 5 min timer
    user.save()

    projects = Project.objects.filter(
        Q(title__icontains=query) |
        Q(description__icontains=query) |
        Q(tags__name__icontains=query)
    ).distinct().prefetch_related('tags', 'taken').select_related('lecturer__user')

    taken_ids   = []
    flagged_ids = []
    has_taken   = False
    if user.is_student:
        try:
            student     = user.student_profile
            taken_ids   = list(ProjectTaken.objects.values_list('project_id', flat=True))
            flagged_ids = list(ProjectFlag.objects.filter(student=student).values_list('project_id', flat=True))
            has_taken   = ProjectTaken.objects.filter(student=student).exists()
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
             'is_flagged':      p.id in taken_ids or p.id in flagged_ids,  # flagged if taken OR manually flagged
        })

    return JsonResponse({
        'results':           results,
        'count':             len(results),
        'credits_remaining': user.search_count,
        'query':             query,
        'has_taken':         has_taken,
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

    if project.status != 'Complete':
        return JsonResponse({'error': 'Only completed projects can be taken.'}, status=400)

    if hasattr(project, 'taken'):
        return JsonResponse({'error': 'This project has already been taken by someone.'}, status=400)

    try:
        student_profile = request.user.student_profile
    except StudentProfile.DoesNotExist:
        return JsonResponse({'error': 'Student profile not found.'}, status=400)

    # Check if this student has already taken a project
    if ProjectTaken.objects.filter(student=student_profile).exists():
        return JsonResponse({'error': 'You have already taken a project. You can only take one.'}, status=400)

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

    # Only allow flagging complete projects
    if project.status != 'Complete':
        return JsonResponse({'error': 'Only completed projects can be flagged.'}, status=400)

    try:
        student_profile = request.user.student_profile
    except StudentProfile.DoesNotExist:
        return JsonResponse({'error': 'Student profile not found.'}, status=400)

    flag, created = ProjectFlag.objects.get_or_create(project=project, student=student_profile)

    if created:
        return JsonResponse({'success': True,  'message': 'Project flagged successfully.'})
    else:
        return JsonResponse({'success': False, 'message': 'You have already flagged this project.'})

# ─────────────────────────────────────────
#  CHECK CREDITS (AJAX)
# ─────────────────────────────────────────

@login_required
def check_credits_view(request):
    user = request.user

    # Reset if 5 minutes have passed
    if user.search_credits_reset_at:
        elapsed = timezone.now() - user.search_credits_reset_at
        if elapsed >= timedelta(minutes=5):
            user.search_count = 10
            user.search_credits_reset_at = None
            user.save()

    return JsonResponse({'credits': user.search_count})