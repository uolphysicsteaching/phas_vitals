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
    "AdminEngagementSummaryView",
    "AdminResultStudentEngagementView",
    "AdminSubmitStudentEngagementView",
    "LabAttendanceUpload",
    "StudentEngagementSummary",
    "SubmitStudentEngagementView",
    # Groups
    "AssignTutorGroupsView",
    "ToggleMeeting",
    "ToggleTutorialAssignmentField",
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
    StudentEngagementSummary,
    SubmitStudentEngagementView,
)
from .groups import (
    AssignTutorGroupsView,
    ToggleMeeting,
    ToggleTutorialAssignmentField,
)

# Create your views here.
