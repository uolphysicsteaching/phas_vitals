"""{{ project_name }} URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.11/topics/http/urls/
"""
from pathlib import Path
# Django imports
from django.conf.urls import include
from django.urls import path, re_path
from django.contrib import admin
from django.contrib.auth import views as auth_views

from .settings.production import PROJECT_ROOT

urlpatterns = [
    # Examples:
    # url(r'^$', '{{ project_name }}.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),

    path('admin/', admin.site.urls),
]

# Add urls path for all the apps
for f in (Path(PROJECT_ROOT)/"apps").iterdir():
    if not f.is_dir() or f.name.startswith("."):
        continue
    if (f/"urls.py").exists():
        urlpatterns.append(path(f"{f.name}/", include(f"{f.name}.urls")))
