"""URL patterns for tutorial app."""

# Python imports
from os.path import basename, dirname

# Django imports
from django.urls import path, re_path

# external imports
import tutorial.views as views

app_name = basename(dirname(__file__))

urlpatterns = [
    # Examples:
    # re_path(r'^$', '{{ tutorial_name }}.views.home', name='home'),
    # re_path(r'^blog/', include('blog.urls')),
    path("admin/assign/<cohort>/", views.AssignTutorGroupsView.as_view()),
    path("admin/assign/", views.AssignTutorGroupsView.as_view()),
    path("admin/ai_upload/", views.AcademicIntegrityUpload.as_view()),
    path("admin/dashboard/<cohort>/", views.AdminDashboardView.as_view()),
    path("admin/dashboard/", views.AdminDashboardView.as_view()),
    path("admin/meetings_summary/<cohort>/", views.MeetingsSummary.as_view()),
    path("admin/meetings_summary/", views.MeetingsSummary.as_view()),
    path("engagement/submit/<session>", views.SubmitStudentEngagementView.as_view()),
    path("engagement_view/", views.ShowEngagementView.as_view()),
    path("engagement_view/<int:semester>/<cohort>/", views.ShowEngagementView.as_view()),
    path("engagement_view/<int:semester>/<cohort>//", views.ShowEngagementView.as_view()),
    path("engagement_view/<int:semester>/<cohort>/<code>/", views.ShowEngagementView.as_view()),
    path(
        "engagement/admin_submit/session_<int:student>_<int:session>", views.AdminSubmitStudentEngagementView.as_view()
    ),
    path(
        "engagement/admin_result/session_<int:student>_<int:session>", views.AdminResultStudentEngagementView.as_view()
    ),
    re_path(
        r"^admin/engagement/(?P<semester>[0-9])?(/(?P<cohort>[^/]*)/?)?$", views.AdminEngagementSummaryView.as_view()
    ),
    path("admin/lab_attendance/", views.LabAttendanceUpload.as_view()),
    path("marking/toggle/<user>/<component>", views.ToggleTutorialAssignmentField.as_view()),
    path("marking/toggle_meeting/<username>/<int:slug>", views.ToggleMeeting.as_view()),
    path("marking_view(/<issid>", views.StudentMarkingSummary.as_view()),
]
