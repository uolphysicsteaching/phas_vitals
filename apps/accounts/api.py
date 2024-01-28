#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""REST Framework API endpoints for accounts app"""

from django.contrib.auth.models import Group
from rest_framework import routers, serializers, viewsets

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
        )


class GroupSerializer(serializers.ModelSerializer):

    """Serialiser for Goup Objects."""

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


class GroupViewSet(viewsets.ReadOnlyModelViewSet):

    """Default ViewSet for Group Objects."""

    queryset = Group.objects.all()
    serializer_class = GroupSerializer


class CohortViewSet(viewsets.ReadOnlyModelViewSet):

    """Default Viewset for Cohort Objects."""

    queryset = Cohort.objects.all()
    serializer_class = CohortSerializer


class ProgrammeViewSet(viewsets.ReadOnlyModelViewSet):

    """Default Viewset for Programme Objects."""

    queryset = Cohort.objects.all()
    serializer_class = ProgrammeSerializer


router = routers.DefaultRouter()
router.register(r"accounts", AccountViewSet)
router.register(r"groups", GroupViewSet)
router.register(r"cohorts", CohortViewSet)
router.register(r"programmes", ProgrammeViewSet)
