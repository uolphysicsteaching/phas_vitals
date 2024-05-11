#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""REST Framework API endpoints for accounts app."""

# Django imports
from django.contrib.auth.models import Group

# external imports
from rest_framework import serializers, viewsets

# app imports
from phas_vitals.api import router

# app imports
from .models import Account, Cohort, Programme


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
            "level",
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


# ViewSets define the view behavior.


class AccountViewSet(viewsets.ReadOnlyModelViewSet):
    """Default Viewset for Account objects."""

    queryset = Account.objects.all()
    serializer_class = AccountSerializer
    filterset_fields = [
        "first_name",
        "last_name",
        "username",
        "programme__name",
        "apt__last_name",
        "is_staff",
        "is_superuser",
    ]


class GroupViewSet(viewsets.ReadOnlyModelViewSet):
    """Default ViewSet for Group Objects."""

    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    filterset_fields = ["name"]


class CohortViewSet(viewsets.ReadOnlyModelViewSet):
    """Default Viewset for Cohort Objects."""

    queryset = Cohort.objects.all()
    serializer_class = CohortSerializer
    filterset_fields = ["name", "code"]


class ProgrammeViewSet(viewsets.ReadOnlyModelViewSet):
    """Default Viewset for Programme Objects."""

    queryset = Programme.objects.all()
    serializer_class = ProgrammeSerializer
    filterset_fields = ["name", "code", "level", "local"]


router.register(r"accounts", AccountViewSet)
router.register(r"groups", GroupViewSet)
router.register(r"cohorts", CohortViewSet)
router.register(r"programmes", ProgrammeViewSet)
