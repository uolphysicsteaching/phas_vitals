"""phas_vitals URL Configuration.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.11/topics/http/urls/
"""

# Python imports
from pathlib import Path

# Django imports
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

# external imports
from ajax_select import urls as ajax_select_urls

# app imports
from .api import router
from .settings.production import PROJECT_ROOT
from .views import E403View, E404View, E500View, HomeView, HtmxLogoutView

# Set Error handlers
handler404 = E404View.as_view()
handler403 = E403View.as_view()
handler500 = E500View.as_view()

urlpatterns = [
    # Examples:
    # url(r'^$', 'phas_vitals.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),
    path("", HomeView.as_view()),
    path("ajax_select/", include(ajax_select_urls)),
    path("riaradh/", admin.site.urls),
    path("api/", include(router.urls)),
    path("api-auth/", include("rest_framework.urls")),
    path("baton/", include("baton.urls")),
    path(r"isteach/", auth_views.LoginView.as_view(), name="core_login"),
    path(r"imigh/", HtmxLogoutView.as_view(next_page="/"), name="core_logout"),
    path("o/", include("oauth2_provider.urls", namespace="oauth2_provider")),
    path("oauth2/", include("django_auth_adfs.urls")),
    path("tinymce/", include("tinymce.urls")),
]

# Add urls path for all the apps
for f in (Path(PROJECT_ROOT) / "apps").iterdir():
    if not f.is_dir() or f.name.startswith("."):
        continue
    if (f / "urls.py").exists():
        urlpatterns.append(path(f"{f.name}/", include(f"{f.name}.urls")))
