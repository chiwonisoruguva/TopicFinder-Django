from django.urls import path
from . import views
 
urlpatterns = [
    # ── Auth ──────────────────────────────────────
    path('register/', views.register_view, name='register'),
    path('verify/', views.verify_view, name='verify'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('delete/', views.delete_account_view, name='delete_account'),
 
    # ── Search ────────────────────────────────────
    path('search/', views.search_view, name='search'),
 
    # ── Project Actions ───────────────────────────
    path('project/<int:project_id>/', views.project_detail_view, name='project_detail'),
    path('project/<int:project_id>/take/', views.take_project_view, name='take_project'),
    path('project/<int:project_id>/flag/', views.flag_project_view, name='flag_project'),
    path('lecturer/dashboard/', views.lecturer_dashboard, name='lecturer_dashboard'),
    path('suggestions/', views.suggestions_list_view, name='suggestions_list'),
    path('add-project/', views.add_project, name='add_project'),
    path('add-suggestion/', views.add_suggestion, name='add_suggestion'),
    path('suggestions/', views.suggestions_list_view, name='suggestions_list'),
    path('check-credits/', views.check_credits_view, name='check_credits'),
]

 