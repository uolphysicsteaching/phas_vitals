#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""REST Framework API endpoints for accounts app."""

# Django imports
from django.contrib.auth.models import Group
from django.db.models import Q

# external imports
from rest_framework import serializers, viewsets
from rest_framework.permissions import IsAdminUser

# app imports
from phas_vitals.api import router

# app imports
from .models import Account, Cohort, Programme, Year


# Serializers define the API representation.
class AccountSerializer(serializers.ModelSerializer):
    """Main Account Serialiser."""

    class Meta:
        model = Account
        fields = (
            "username",
            "title",
            "first_name",
            "last_name",
            "email",
            "year",
            "programme",
            "apt",
            "registration_status",
            "is_staff",
            "is_superuser",
        )


class GroupSerializer(serializers.ModelSerializer):
    """Serialiser for Group Objects."""

    class Meta:
        model = Group
        fields = ("name",)


class ProgrammeSerializer(serializers.ModelSerializer):
    """Serialiser for Programmes."""

    class Meta:
        model = Programme
        fields = ("name", "code")


class CohortSerializer(serializers.ModelSerializer):
    """Serialiser for Student Cohorts."""

    representation = serializers.CharField(max_length=20, read_only=True, source="__str__")

    class Meta:
        model = Cohort
        fields = ("name", "representation")


class YearSerializer(serializers.ModelSerializer):
    """Serialiser for Years."""

    class Meta:
        model = Year
        fields = ("name", "status", "level")


# ViewSets define the view behavior.


def scoped_accounts_for_user(user):
    """Return accounts visible to a staff API caller."""
    if user.is_superuser:
        return Account.objects.all()
    return (
        Account.objects.filter(
            Q(pk=user.pk)
            | Q(school__managers=user)
            | Q(programme__school__managers=user)
            | Q(module_enrollments__module__module_leader=user)
            | Q(module_enrollments__module__team_members=user)
            | Q(tutorial_group__tutor=user)
        )
        .distinct()
        .select_related("programme", "school", "year")
    )


class StaffReadOnlyModelViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only API viewset with explicit staff-only permissions."""

    permission_classes = [IsAdminUser]


class AccountViewSet(StaffReadOnlyModelViewSet):
    """Default Viewset for Account objects."""

    queryset = Account.objects.none()
    serializer_class = AccountSerializer
    filterset_fields = [
        "first_name",
        "last_name",
        "username",
        "programme__name",
        "is_staff",
        "is_superuser",
    ]

    def get_queryset(self):
        """Scope account records to users the staff caller is responsible for."""
        return scoped_accounts_for_user(self.request.user)


class YearViewSet(StaffReadOnlyModelViewSet):
    """Default Viewset for Cohort Objects."""

    queryset = Year.objects.all()
    serializer_class = YearSerializer
    filterset_fields = ["name", "status", "level"]


class GroupViewSet(StaffReadOnlyModelViewSet):
    """Default ViewSet for Group Objects."""

    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    filterset_fields = ["name"]


class CohortViewSet(StaffReadOnlyModelViewSet):
    """Default Viewset for Cohort Objects."""

    queryset = Cohort.objects.all()
    serializer_class = CohortSerializer
    filterset_fields = ["name", "code"]


class ProgrammeViewSet(StaffReadOnlyModelViewSet):
    """Default Viewset for Programme Objects."""

    queryset = Programme.objects.all()
    serializer_class = ProgrammeSerializer
    filterset_fields = ["name", "code", "level", "local"]


router.register(r"accounts", AccountViewSet)
router.register(r"groups", GroupViewSet)
router.register(r"cohorts", CohortViewSet)
router.register(r"programmes", ProgrammeViewSet)
