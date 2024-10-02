# Python imports
from os.path import basename, dirname

# Django imports
from django.urls import path

# app imports
from . import views

app_name = basename(dirname(__file__))

urlpatterns = [
    path("tutor_email/", views.TutorGroupEmailsView.as_view(), name="tutor_send_email"),
    path("detail/<int:number>/", views.StudentSummaryView.as_view(), name="student_detail"),
    path("change-password/", views.ChangePasswordView.as_view(), name="change_password"),
    path("tools/student_list/", views.CohortFilterActivityScoresView.as_view(), name="cohort_activity_list"),
    path("student_lookup", views.StudentAutocomplete.as_view(), name="Student_lookup"),
    path("staff_lookup", views.StaffAutocomplete.as_view(), name="Staff_lookup"),
]
