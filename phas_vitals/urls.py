"""phas_vitals URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.11/topics/http/urls/
"""
# Python imports
from pathlib import Path

# Django imports
from django.conf.urls import include
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, re_path
from django.views.generic import TemplateView

# app imports
from .api import router
from .settings.production import PROJECT_ROOT

urlpatterns = [
    # Examples:
    # url(r'^$', 'phas_vitals.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),
    path("", TemplateView.as_view(template_name="home.html")),
    path("admin/", admin.site.urls),
    path("api/", include(router.urls)),
    path("api-auth/", include("rest_framework.urls")),
    path("baton/", include("baton.urls")),
    path(r"login/", auth_views.LoginView.as_view(), name="core_login"),
    path(r"logout/", auth_views.LogoutView.as_view(next_page="/"), name="core_logout"),
    path("o/", include("oauth2_provider.urls", namespace="oauth2_provider")),
]

# Add urls path for all the apps
for f in (Path(PROJECT_ROOT) / "apps").iterdir():
    if not f.is_dir() or f.name.startswith("."):
        continue
    if (f / "urls.py").exists():
        urlpatterns.append(path(f"{f.name}/", include(f"{f.name}.urls")))
