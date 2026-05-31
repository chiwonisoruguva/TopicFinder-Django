from django.urls import path
from . import views

urlpatterns = [
    # ── Auth ──────────────────────────────────────
    path('register/', views.register_view, name='register'),
    path('verify/',   views.verify_view,   name='verify'),
    path('login/',    views.login_view,    name='login'),
    path('logout/',   views.logout_view,   name='logout'),
    path('delete/',   views.delete_account_view, name='delete_account'),

    # ── Student Dashboard ─────────────────────────
    path('dashboard/', views.dashboard_view, name='dashboard'),

    # ── Search ────────────────────────────────────
    path('search/', views.search_view, name='search'),

    # ── Project Actions ───────────────────────────
    path('project/<int:project_id>/take/', views.take_project_view, name='take_project'),
    path('project/<int:project_id>/flag/', views.flag_project_view, name='flag_project'),

    # ── Lecturer ──────────────────────────────────
    path('lecturer/dashboard/',      views.lecturer_dashboard_view, name='lecturer_dashboard'),
    path('lecturer/add-project/',    views.add_project_view,        name='add_project'),
    path('lecturer/add-suggestion/', views.add_suggestion_view,     name='add_suggestion'),

    # ── Suggestions ───────────────────────────────

    path('suggestions/', views.suggestions_page_view, name='suggestions'),
    path('suggestions/data/', views.suggestions_view, name='suggestions_data'),
    path('check-credits/', views.check_credits_view, name='check_credits'),
]