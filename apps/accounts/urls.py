# Python imports
from os.path import basename, dirname

# Django imports
from django.urls import path

# app imports
from . import views

app_name = basename(dirname(__file__))

urlpatterns = [
    path("tutor_email/", views.TutorGroupEmailsView.as_view()),
]
