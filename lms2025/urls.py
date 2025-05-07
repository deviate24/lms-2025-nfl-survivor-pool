"""
URL configuration for lms2025 project.
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(pattern_name='home'), name='index'),
    path('pool/', include('pool.urls')),
    path('users/', include('users.urls')),
]
