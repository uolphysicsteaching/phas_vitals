#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Project app views module handles all views of tutorial objects and marks."""

__all__ = [
    # Admin
    "AcademicIntegrityUpload",
    "AdminDashboardView",
    "MeetingsSummary",
    "StudentMarkingSummary",
    # Engagement
    "ShowEngagementView",
    "AdminEngagementSummaryView",
    "AdminResultStudentEngagementView",
    "AdminSubmitStudentEngagementView",
    "LabAttendanceUpload",
    "TutorStudentEngagementSummary",
    "SubmitStudentEngagementView",
    # Groups
    "AssignTutorGroupsView",
    "ToggleTutorialAssignmentField",
    # Meeting records
    "MeetingDetailView",
    "MeetingManageCreateView",
    "MeetingManageDeleteView",
    "MeetingManageListView",
    "MeetingManageUpdateView",
    "MeetingAttendanceCreateView",
    "MeetingAttendanceActionView",
    "MeetingAttendanceDeleteView",
    "MeetingAttendanceDetailView",
    "MeetingAttendanceUpdateView",
    "QuestionManageCreateView",
    "QuestionManageDeleteView",
    "QuestionManageListView",
    "QuestionManageUpdateView",
]

# app imports
from .admin import (
    AcademicIntegrityUpload,
    AdminDashboardView,
    MeetingsSummary,
    StudentMarkingSummary,
)
from .engagement import (
    AdminEngagementSummaryView,
    AdminResultStudentEngagementView,
    AdminSubmitStudentEngagementView,
    LabAttendanceUpload,
    ShowEngagementView,
    SubmitStudentEngagementView,
    TutorStudentEngagementSummary,
)
from .groups import AssignTutorGroupsView, ToggleTutorialAssignmentField
from .meetings import (
    MeetingAttendanceActionView,
    MeetingAttendanceCreateView,
    MeetingAttendanceDeleteView,
    MeetingAttendanceDetailView,
    MeetingAttendanceUpdateView,
    MeetingDetailView,
    MeetingManageCreateView,
    MeetingManageDeleteView,
    MeetingManageListView,
    MeetingManageUpdateView,
    QuestionManageCreateView,
    QuestionManageDeleteView,
    QuestionManageListView,
    QuestionManageUpdateView,
)

# Create your views here.
