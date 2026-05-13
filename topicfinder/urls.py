from django.contrib import admin
from django.urls import path, include
from accounts import views as account_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('dashboard/', account_views.dashboard_view, name='dashboard'),
    path('', account_views.login_view, name='home'),
    path('', include('accounts.urls')),
   
]
