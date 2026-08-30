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
    path(
        "admin/meetings_summary/<cohort>/",
        views.MeetingsSummary.as_view(),
        name="meetings-summary-cohort",
    ),
    path(
        "admin/meetings_summary/",
        views.MeetingsSummary.as_view(),
        name="meetings-summary",
    ),
    path(
        "meetings/<int:pk>/",
        views.MeetingDetailView.as_view(),
        name="meeting-detail",
    ),
    path(
        "manage/meetings/",
        views.MeetingManageListView.as_view(),
        name="meeting-manage-list",
    ),
    path(
        "manage/meetings/create/",
        views.MeetingManageCreateView.as_view(),
        name="meeting-manage-create",
    ),
    path(
        "manage/meetings/<int:pk>/edit/",
        views.MeetingManageUpdateView.as_view(),
        name="meeting-manage-update",
    ),
    path(
        "manage/meetings/<int:pk>/delete/",
        views.MeetingManageDeleteView.as_view(),
        name="meeting-manage-delete",
    ),
    path(
        "manage/questions/",
        views.QuestionManageListView.as_view(),
        name="question-manage-list",
    ),
    path(
        "manage/questions/create/",
        views.QuestionManageCreateView.as_view(),
        name="question-manage-create",
    ),
    path(
        "manage/questions/<int:pk>/edit/",
        views.QuestionManageUpdateView.as_view(),
        name="question-manage-update",
    ),
    path(
        "manage/questions/<int:pk>/delete/",
        views.QuestionManageDeleteView.as_view(),
        name="question-manage-delete",
    ),
    path(
        "meetings/<int:meeting_pk>/students/<int:student_pk>/",
        views.MeetingAttendanceActionView.as_view(),
        name="meeting-attendance-action",
    ),
    path(
        "meetings/<int:meeting_pk>/students/<int:student_pk>/create/",
        views.MeetingAttendanceCreateView.as_view(),
        name="meeting-attendance-create",
    ),
    path(
        "meeting-records/<int:pk>/",
        views.MeetingAttendanceDetailView.as_view(),
        name="meeting-attendance-detail",
    ),
    path(
        "meeting-records/<int:pk>/edit/",
        views.MeetingAttendanceUpdateView.as_view(),
        name="meeting-attendance-update",
    ),
    path(
        "meeting-records/<int:pk>/delete/",
        views.MeetingAttendanceDeleteView.as_view(),
        name="meeting-attendance-delete",
    ),
    path("engagement/submit/<session>", views.SubmitStudentEngagementView.as_view()),
    path("engagement_view/", views.ShowEngagementView.as_view()),
    path("engagement_view/<int:semester>/<cohort>/", views.ShowEngagementView.as_view()),
    path("engagement_view/<int:semester>/<cohort>//", views.ShowEngagementView.as_view()),
    path(
        "engagement_view/<int:semester>/<cohort>/<code>/",
        views.ShowEngagementView.as_view(),
    ),
    path(
        "engagement/admin_submit/session_<int:student>_<int:session>",
        views.AdminSubmitStudentEngagementView.as_view(),
    ),
    path(
        "engagement/admin_result/session_<int:student>_<int:session>",
        views.AdminResultStudentEngagementView.as_view(),
    ),
    re_path(
        r"^admin/engagement/(?P<semester>[0-9])?(/(?P<cohort>[^/]*)/?)?$",
        views.AdminEngagementSummaryView.as_view(),
    ),
    path("admin/lab_attendance/", views.LabAttendanceUpload.as_view()),
    path(
        "marking/toggle/<user>/<component>",
        views.ToggleTutorialAssignmentField.as_view(),
    ),
    path("marking_view(/<issid>", views.StudentMarkingSummary.as_view()),
]
