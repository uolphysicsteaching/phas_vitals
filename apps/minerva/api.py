# -*- coding: utf-8 -*-
"""Django REST framework API file."""

# Python imports
import logging
from operator import attrgetter

# Django imports
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.utils import timezone as tz
from django.utils.encoding import smart_str

# external imports
from accounts.models import Account
from django_filters import rest_framework as filters
from rest_framework import routers, serializers, status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.schemas import get_schema_view
from util.backend import HMACAuthentication

# app imports
from phas_vitals.api import router

# app imports
from .models import Module, Test, Test_Attempt, Test_Score

logger = logging.getLogger("drf_authentication")
logger.debug("*" * 80)


class TenPerPagePagination(PageNumberPagination):
    page_size = 10


class CompoundSlugRelatedField(serializers.SlugRelatedField):
    """Subclass a SlugRelatedField so it can optionall do multiple lookups"""

    def to_internal_value(self, data):
        queryset = self.get_queryset()
        try:
            slugs = self.slug_field.split("~")
            data = data.split("~")
            query = {k: v for k, v in zip(slugs, data)}
            return queryset.get(**query)
        except ObjectDoesNotExist:
            self.fail("does_not_exist", slug_name=self.slug_field, value=smart_str(data))
        except (TypeError, ValueError):
            self.fail("invalid")

    def to_representation(self, obj):
        slugs = self.slug_field.split("~")
        out = []
        for slug in slugs:
            if "__" in slug:
                # handling nested relationship if defined
                slug = slug.replace("__", ".")
            out.append(attrgetter(slug)(obj))
        return "~".join(out)


###### Serializers define the API representation. ########


class ModuleSerializer(serializers.ModelSerializer):
    """Serialises minerva.Module."""

    class Meta:
        model = Module
        fields = [x.name for x in model._meta.fields]


class TestSerializer(serializers.ModelSerializer):
    """Serialises minerva.Test."""

    class Meta:
        model = Test
        fields = [x.name for x in model._meta.fields]


class TestAttemptSerializer(serializers.ModelSerializer):
    """Serialises minerva.Test_Attmept."""

    class Meta:
        model = Test_Attempt
        fields = [x.name for x in model._meta.fields]


class TestScoreSerializer(serializers.ModelSerializer):
    """Serialises minerva.Test_Score."""

    class Meta:
        model = Test_Score
        fields = [x.name for x in model._meta.fields]


###### Viewsets #########################################


class ModuleViewSet(viewsets.ReadOnlyModelViewSet):
    """Default Viewset for Account objects."""

    queryset = Module.objects.all()
    serializer_class = ModuleSerializer


class TestViewSet(viewsets.ReadOnlyModelViewSet):
    """Default Viewset for Account objects."""

    queryset = Test.objects.all()
    serializer_class = TestSerializer


class TestAttemptViewSet(viewsets.ReadOnlyModelViewSet):
    """Default Viewset for Account objects."""

    queryset = Test_Attempt.objects.all()
    serializer_class = TestAttemptSerializer


class TestScoreViewSet(viewsets.ReadOnlyModelViewSet):
    """Default Viewset for Account objects."""

    queryset = Test_Score.objects.all()
    serializer_class = TestScoreSerializer


class FeedbackPermission(BasePermission):
    """Ensure nobody has permissions to delete stuff via the API."""

    def has_permission(self, request, view):
        """Allow read and write, but block delete."""
        logger.debug(f"Checking for allowed method - {request.method=}")
        if request.method == "DELETE":
            logger.debug("Tried calling a DELETE method - not allowed!")
            return False
        return True


class IsSuperuserOrHMACAuthenticated(BasePermission):
    """Enforce that the user making the request is either a superuser, or the request is singed with a valid key."""

    def has_permission(self, request, view):
        """Do the permission check."""
        user = request.user
        logger.debug("Checking User permissions:")
        # Allow if user is a superuser
        if user and user.is_superuser and not getattr(user, "hmac_authenticated", False):
            logger.debug("User is super user with non HMAC call")
            return True
        # Allow if HMACAuthentication has successfully authenticated the user
        logger.debug("Checking for HMAC authentication")
        logger.debug(f"{user=} {user.is_authenticated=} {getattr(user, 'hmac_authenticated', False)=} ")
        return user and user.is_authenticated and getattr(user, "hmac_authenticated", False)


# Serializers define the API representation.
class FeedbackSerializer(serializers.ModelSerializer):
    """Serialize/Deserialize Feedback items."""

    student = serializers.SlugRelatedField(slug_field="username", queryset=Account.objects.all(), source="user")
    assignment_name = CompoundSlugRelatedField(
        slug_field="module__code~name", queryset=Test.objects.all(), source="test"
    )
    comment = serializers.CharField(required=False)
    date = serializers.DateTimeField(required=False)

    class Meta:
        model = Test_Score
        fields = ("student", "assignment_name", "comment", "score", "date")

    def get_unique_together_constraints(self, model):
        """Hack to stop the Serialiser thinking we've got unique constraints."""
        yield from []

    def get_existing_instance(self, validated_data):
        """Get an instance if it already exists."""
        return Test_Score.objects.filter(user=validated_data["user"], test=validated_data["test"]).first()

    def create(self, validated_data):
        """Add new tags - uses the test.add_attempt() method."""
        test = validated_data["test"]
        instance, attempt = test.add_attempt(
            validated_data["user"],
            validated_data["score"],
            date=validated_data["date"],
            text=validated_data["comment"],
        )
        instance.status = "Graded"
        instance.save()
        attempt.status = "Completed"
        attempt.save()

        return instance

    def update(self, instance, validated_data):
        instance.comment = validated_data["comment"]
        instance.score = validated_data["score"]
        instance.date = validated_data["date"]
        instance.save()
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        last = instance.attempts.last()
        if last:
            data["comment"] = last.text
            data["date"] = last.attempted
        return data


class FeedbackFilters(filters.FilterSet):

    class Meta:
        model = Test_Score
        fields = ["user", "test", "score"]

    score = filters.NumberFilter(field_name="score", lookup_expr="gte")
    user = filters.CharFilter(method="filter_student")
    test = filters.CharFilter(method="filter_test")

    def filter_student(self, queryset, name, value):
        try:
            value = int(value)
            return queryset.filter(Q(user__pk=value))
        except (ValueError, TypeError):
            return queryset.filter(
                Q(user__username__icontains=value)
                | Q(user__first_name__icontains=value)
                | Q(user__last_name__icontains=value)
            )

    def filter_test(self, queryset, name, value):
        try:
            value = int(value)
            return queryset.filter(Q(test__pk=value))
        except (ValueError, TypeError):
            return queryset.filter(
                Q(test__test_id__icontains=value)
                | Q(test_name__icontains=value)
                | Q(test__category__text__icontains=value)
            )


class FeednackViewSet(viewsets.ModelViewSet):
    """Viewset for the Feedback Objects."""

    serializer_class = FeedbackSerializer
    queryset = Test_Score.objects.all()
    filterset_class = FeedbackFilters
    search_fields = ["assignment_name", "comment", "student__last_name", "student__username"]
    lookup_field = "id"
    permission_classes = [FeedbackPermission, IsSuperuserOrHMACAuthenticated]
    authentication_classes = [HMACAuthentication]
    pagination_class = TenPerPagePagination

    def paginate_queryset(self, queryset):
        if self.request.accepted_renderer.format == "json":
            return None  # disables pagination
        return super().paginate_queryset(queryset)


router.register(r"feedback", FeednackViewSet, basename="feedback")
router.register(r"modules", ModuleViewSet)
router.register(r"tests", TestViewSet)
router.register(r"test_attempts", TestAttemptViewSet)
router.register(r"test_scores", TestScoreViewSet)
schema_view = get_schema_view(title="VITALs API")
