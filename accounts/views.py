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
from .models import CustomUser, Project, ProjectTaken, ProjectFlag, StudentProfile, LecturerProfile, ProjectSuggestion
from .models import ProjectSuggestion

# ─────────────────────────────────────────
#  REGISTER
# ─────────────────────────────────────────

def register_view(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        password = request.POST.get('password')

        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, 'Email is already registered.')
            return redirect('register')

        code = str(random.randint(1000, 9999))
        expires = timezone.now() + timedelta(minutes=10)

        user = CustomUser.objects.create_user(
            username=email, email=email, password=password,
            first_name=name, verification_code=code,
            verification_code_expires=expires, is_verified=False,
        )

        send_mail(
            'Your TopicFinder Verification Code',
            f'Hi {name},\n\nYour verification code is: {code}\n\nThis code expires in 10 minutes.',
            None, [email], fail_silently=False,
        )

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
        email = request.POST.get('email')
        password = request.POST.get('password')
        selected_role = request.POST.get('role')  # This comes from the toggle we will add to the HTML

        try:
            # 1. Check if user exists
            user = CustomUser.objects.get(email=email)

            # 2. Check Verification (your existing logic)
            if not user.is_verified:
                messages.error(request, 'Please verify your email before logging in.')
                return redirect('login')

            # 3. Security Check: Does their account role match their selection?
            if user.role != selected_role:
                messages.error(request, f'This account is not registered as a {selected_role}.')
                return redirect('login')

            # 4. Authenticate
            auth_user = authenticate(request, username=email, password=password)

            if auth_user is not None:
                request.session.flush()  # clears any old session data
                login(request, auth_user)
            # 5. Route to the correct dashboard
                if auth_user.is_lecturer:
                    return redirect('lecturer_dashboard')
                else:
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
#  DASHBOARD
# ─────────────────────────────────────────


def dashboard_view(request):
    if not request.user.is_authenticated:
        return redirect('login')
    if not request.user.is_verified:
        return redirect('login')

    # Reset credits if 5 minutes have passed
    now = timezone.now()
    if now > request.user.last_search_time + timedelta(minutes=5):
        request.user.search_count = 10
        request.user.last_search_time = now
        request.user.save()
        print("CREDITS RESET!")

    suggestions = ProjectSuggestion.objects.all().order_by('-id')[:5]

    return render(request, 'dashboard.html', {
        'user': request.user,
        'suggestions': suggestions
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
#  SEARCH (AJAX — returns JSON)
# ─────────────────────────────────────────

@login_required
def search_view(request):
    query = request.GET.get('q', '').strip().lower()
    now = timezone.now()

    # Synonym mapping so abbreviations find the right results
    SYNONYMS = {
        'ml': 'machine learning',
        'ai': 'artificial intelligence',
        'nlp': 'natural language processing',
        'dl': 'deep learning',
        'cv': 'computer vision',
        'db': 'database',
        'os': 'operating systems',
        'hci': 'human computer interaction',
        'ux': 'user experience',
        'ui': 'user interface',
        'iot': 'internet of things',
        'se': 'software engineering',
    }
    query = SYNONYMS.get(query, query)

    # Reset credits every 5 minutes
    if now > request.user.last_search_time + timedelta(minutes=5):
        request.user.search_count = 10
        request.user.last_search_time = now
        request.user.save()

    if not query:
        return JsonResponse({'error': 'Please enter a search term.'}, status=400)

    if request.user.search_count <= 0:
        return JsonResponse({'error': 'You have used all your search credits.'}, status=403)

    # Deduct one credit
    request.user.search_count -= 1
    request.user.save()

    projects = Project.objects.filter(
        Q(title__icontains=query) |
        Q(description__icontains=query) |
        Q(category__icontains=query) |
        Q(tags__name__icontains=query)
    ).distinct().prefetch_related('tags', 'taken').select_related('lecturer__user')

    taken_ids = []
    flagged_ids = []
    if request.user.is_student:
        try:
            student = request.user.student_profile
            taken_ids = list(ProjectTaken.objects.values_list('project_id', flat=True))
            flagged_ids = list(ProjectFlag.objects.filter(student=student).values_list('project_id', flat=True))
        except StudentProfile.DoesNotExist:
            pass

    results = []
    for p in projects:
        lecturer_name = ''
        department = ''
        if p.lecturer:
            lecturer_name = p.lecturer.user.get_full_name()
            department = p.lecturer.department

        results.append({
            'id': p.id,
            'title': p.title,
            'description': p.description,
            'year': p.year,
            'status': p.status,
            'recommendations': p.recommendations,
            'tags': [t.name for t in p.tags.all()],
            'lecturer': lecturer_name,
            'department': department,
            'is_taken': p.id in taken_ids,
            'is_flagged': p.id in flagged_ids,
        })

    return JsonResponse({
        'results': results,
        'count': len(results),
        'credits_remaining': request.user.search_count,
        'query': query,
    })


# ─────────────────────────────────────────
#  PROJECT DETAIL
# ─────────────────────────────────────────

@login_required
def project_detail_view(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    
    is_taken = False
    is_flagged = False
    
    if request.user.is_student:
        try:
            student = request.user.student_profile
            is_taken = ProjectTaken.objects.filter(project=project, student=student).exists()
            is_flagged = ProjectFlag.objects.filter(project=project, student=student).exists()
        except StudentProfile.DoesNotExist:
            pass
    
    context = {
        'project': project,
        'is_taken': is_taken,
        'is_flagged': is_flagged,
    }
    
    return render(request, 'project_detail.html', context)


# ─────────────────────────────────────────
#  TAKE PROJECT (AJAX — POST)
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


@login_required
def take_project(request, project_id):
    try:
        student = request.user.studentprofile  # This is likely the line failing
        # ... logic to assign project
    except StudentProfile.DoesNotExist:
        return HttpResponse("Student profile not found") # Or a redirect
# ─────────────────────────────────────────
#  FLAG PROJECT (AJAX — POST)
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
        return JsonResponse({'success': True, 'message': 'Project flagged successfully.'})
    else:
        return JsonResponse({'success': False, 'message': 'You have already flagged this project.'})
    
@login_required
def lecturer_dashboard(request):
    # Security: If a student types this URL, kick them back to the student dashboard
    if not request.user.is_lecturer:
        return redirect('dashboard')
    
    # Get the lecturer's profile info from your LecturerProfile model
    # related_name='lecturer_profile' was defined in your models.py
    profile = get_object_or_404(LecturerProfile, user=request.user)
    
    # Get only projects where THIS lecturer is the supervisor
    my_projects = Project.objects.filter(lecturer=profile)

    return render(request, 'lecturer_dashboard.html', {
        'profile': profile,
        'projects': my_projects
    })

# Handle adding a full project
@login_required
def add_project(request):
    if not request.user.is_lecturer:
        return redirect('dashboard')
    
    if request.method == 'POST':
        # Get the lecturer profile linked to this user
        profile = get_object_or_404(LecturerProfile, user=request.user)
        
        # Create the project in MySQL
        Project.objects.create(
            title=request.POST.get('title'),
            description=request.POST.get('description'),
            year=request.POST.get('year'),
            status=request.POST.get('status'),
            lecturer=profile
        )
        messages.success(request, "Project published successfully!")
    return redirect('lecturer_dashboard')

# Handle adding a quick suggestion
@login_required
def add_suggestion(request):
    if not request.user.is_lecturer:
        return redirect('dashboard')
    
    if request.method == 'POST':
        profile = get_object_or_404(LecturerProfile, user=request.user)
        
        ProjectSuggestion.objects.create(
            title=request.POST.get('title'),
            brief_description=request.POST.get('brief_description'),
            suggested_by=profile
        )
        messages.success(request, "Idea posted for students to see!")
    return redirect('lecturer_dashboard')

@login_required
def suggestions_list_view(request):
    # This view shows students all the quick ideas posted by lecturers
    suggestions = ProjectSuggestion.objects.all().order_by('-created_at')
    return render(request, 'suggestions_list.html', {'suggestions': suggestions})

@login_required
def suggestions_list_view(request):
    from .models import ProjectSuggestion
    suggestions = ProjectSuggestion.objects.all()
    return render(request, 'suggestions_list.html', {'suggestions': suggestions})

@login_required
def dashboard_view(request):
    if not request.user.is_verified:
        return redirect('login')
        
    # FETCH DATA FROM MYSQL
    # Get the 5 most recent suggestions to show on the sidebar
    suggestions = ProjectSuggestion.objects.all().order_by('-id')[:5]
    
    return render(request, 'dashboard.html', {
        'user': request.user,
        'suggestions': suggestions # Pass them to the HTML
    })


def suggestions_list_view(request):
    # This gets all suggestions from the database
    suggestions = ProjectSuggestion.objects.all().order_by('-created_at')
    
    return render(request, 'suggestions_list.html', {
        'suggestions': suggestions
    })

@login_required
def check_credits_view(request):
    now = timezone.now()
    if now > request.user.last_search_time + timedelta(minutes=5):
        request.user.search_count = 10
        request.user.last_search_time = now
        request.user.save()
    return JsonResponse({'credits': request.user.search_count})  