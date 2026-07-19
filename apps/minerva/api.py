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
from rest_framework import mixins, serializers, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import BasePermission, IsAdminUser
from rest_framework.schemas import get_schema_view
from util.backend import HMACAuthentication

# app imports
from phas_vitals.api import router

# app imports
from .models import Module, Test, Test_Attempt, Test_Score

logger = logging.getLogger("drf_authentication")
logger.debug("*" * 80)


class TenPerPagePagination(PageNumberPagination):
    """Pagination class that displays 10 items per page."""

    page_size = 10


class CompoundSlugRelatedField(serializers.SlugRelatedField):
    """Subclass a SlugRelatedField so it can optionall do multiple lookups"""

    def to_internal_value(self, data):
        """Convert compound slug data to model instance.

        Args:
            data (str): Slug data with values separated by ~.

        Returns:
            Model instance matching the compound slug.

        Raises:
            ValidationError: If object does not exist or data is invalid.
        """
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
        """Convert model instance to compound slug representation.

        Args:
            obj: The model instance to represent.

        Returns:
            (str): Compound slug string with values separated by ~.
        """
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


def module_scope_for_user(user):
    """Return a Q object restricting modules to those a staff user is responsible for."""
    return Q(module_leader=user) | Q(team_members=user) | Q(school__managers=user)


def scoped_modules_for_user(user):
    """Return modules visible to a staff API caller."""
    qs = Module.objects.all()
    if user.is_superuser:
        return qs
    return qs.filter(module_scope_for_user(user)).distinct()


class ScopedStaffReadOnlyModelViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only API viewset with explicit staff-only permissions and scoped querysets."""

    permission_classes = [IsAdminUser]


class ModuleViewSet(ScopedStaffReadOnlyModelViewSet):
    """Default viewset for Module objects."""

    queryset = Module.objects.none()
    serializer_class = ModuleSerializer

    def get_queryset(self):
        """Scope module records to modules the staff caller is responsible for."""
        return scoped_modules_for_user(self.request.user)


class TestViewSet(ScopedStaffReadOnlyModelViewSet):
    """Default Viewset for Account objects."""

    queryset = Test.objects.none()
    serializer_class = TestSerializer

    def get_queryset(self):
        """Scope test records to tests on visible modules."""
        user = self.request.user
        qs = Test.objects.all()
        if user.is_superuser:
            return qs
        return qs.filter(module__in=scoped_modules_for_user(user)).distinct()


class TestAttemptViewSet(ScopedStaffReadOnlyModelViewSet):
    """Default Viewset for Account objects."""

    queryset = Test_Attempt.objects.none()
    serializer_class = TestAttemptSerializer

    def get_queryset(self):
        """Scope attempt records to attempts on visible modules."""
        user = self.request.user
        qs = Test_Attempt.objects.select_related("test_entry__test__module", "test_entry__user")
        if user.is_superuser:
            return qs
        return qs.filter(test_entry__test__module__in=scoped_modules_for_user(user)).distinct()


class TestScoreViewSet(ScopedStaffReadOnlyModelViewSet):
    """Default Viewset for Account objects."""

    queryset = Test_Score.objects.none()
    serializer_class = TestScoreSerializer

    def get_queryset(self):
        """Scope score records to scores on visible modules."""
        user = self.request.user
        qs = Test_Score.objects.select_related("test__module", "user")
        if user.is_superuser:
            return qs
        return qs.filter(test__module__in=scoped_modules_for_user(user)).distinct()


class FeedbackPermission(BasePermission):
    """Allow only the feedback methods the API intentionally supports."""

    def has_permission(self, request, view):
        """Restrict the endpoint to safe reads plus create and update operations."""
        allowed_methods = {"GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH"}
        allowed = request.method in allowed_methods
        if not allowed:
            logger.debug("Rejected unsupported feedback API method %s", request.method)
        return allowed


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

    def validate(self, attrs):
        """Keep HMAC-authenticated writes scoped to the authenticated student."""
        request = self.context.get("request")
        if request is not None and getattr(request.user, "hmac_authenticated", False):
            target_user = attrs.get("user")
            if target_user is None and self.instance is not None:
                target_user = self.instance.user
            if target_user != request.user:
                raise serializers.ValidationError("HMAC feedback can only be submitted for the authenticated student.")
        return attrs

    def get_existing_instance(self, validated_data):
        """Get an instance if it already exists."""
        return Test_Score.objects.filter(user=validated_data["user"], test=validated_data["test"]).first()

    def create(self, validated_data):
        """Add new tags - uses the test.add_attempt() method."""
        test = validated_data["test"]
        instance, attempt = test.add_attempt(
            validated_data["user"],
            validated_data["score"],
            date=validated_data.get("date"),
            text=validated_data.get("comment"),
        )
        instance.status = "Graded"
        instance.save()
        attempt.status = "Completed"
        attempt.save()

        return instance

    def update(self, instance, validated_data):
        """Update a Test_Score instance with validated data.

        Args:
            instance: The Test_Score instance to update.
            validated_data (dict): The validated data for update.

        Returns:
            The updated Test_Score instance.
        """
        comment = validated_data.get("comment")
        attempted = validated_data.get("date")
        score = validated_data.get("score", instance.score)
        instance.score = score
        instance.save()
        attempt = instance.attempts.order_by("-attempted", "-pk").first()
        if attempt is None:
            instance, _ = instance.test.add_attempt(
                instance.user,
                score,
                date=attempted or tz.now(),
                text=comment,
            )
            return instance

        attempt.score = score
        if comment is not None:
            attempt.text = comment
        if attempted is not None:
            attempt.attempted = attempted
        if attempt.created is None:
            attempt.created = tz.now()
        attempt.modified = tz.now()
        attempt.save()
        return instance

    def to_representation(self, instance):
        """Convert Test_Score instance to dictionary representation.

        Args:
            instance: The Test_Score instance to represent.

        Returns:
            (dict): Dictionary representation with latest attempt details.
        """
        data = super().to_representation(instance)
        last = instance.attempts.last()
        if last:
            data["comment"] = last.text
            data["date"] = last.attempted
        return data


class FeedbackFilters(filters.FilterSet):
    """FilterSet for Test_Score feedback with custom filtering."""

    class Meta:
        model = Test_Score
        fields = ["user", "test", "score"]

    score = filters.NumberFilter(field_name="score", lookup_expr="gte")
    user = filters.CharFilter(method="filter_student")
    test = filters.CharFilter(method="filter_test")

    def filter_student(self, queryset, name, value):
        """Filter queryset by student ID or name.

        Args:
            queryset: The queryset to filter.
            name (str): The field name.
            value: The filter value (ID or name).

        Returns:
            (QuerySet): Filtered queryset matching the student criteria.
        """
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
        """Filter queryset by test ID or name.

        Args:
            queryset: The queryset to filter.
            name (str): The field name.
            value: The filter value (ID or name).

        Returns:
            (QuerySet): Filtered queryset matching the test criteria.
        """
        try:
            value = int(value)
            return queryset.filter(Q(test__pk=value))
        except (ValueError, TypeError):
            return queryset.filter(
                Q(test__test_id__icontains=value)
                | Q(test__name__icontains=value)
                | Q(test__category__text__icontains=value)
            )


class FeednackViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Viewset for the Feedback Objects."""

    serializer_class = FeedbackSerializer
    queryset = Test_Score.objects.none()
    filterset_class = FeedbackFilters
    search_fields = ["assignment_name", "comment", "student__last_name", "student__username"]
    lookup_field = "id"
    permission_classes = [FeedbackPermission, IsSuperuserOrHMACAuthenticated]
    authentication_classes = [HMACAuthentication]
    pagination_class = TenPerPagePagination
    http_method_names = ["get", "head", "options", "post", "put", "patch"]

    def get_queryset(self):
        """Scope feedback records by caller role and HMAC identity."""
        user = self.request.user
        qs = Test_Score.objects.select_related("test__module", "user")
        if getattr(user, "hmac_authenticated", False):
            return qs.filter(user=user)
        if user.is_superuser:
            return qs
        return qs.filter(test__module__in=scoped_modules_for_user(user)).distinct()

    def paginate_queryset(self, queryset):
        """Override pagination to disable for JSON format.

        Args:
            queryset: The queryset to paginate.

        Returns:
            Paginated queryset or None for JSON format.
        """
        if self.request.accepted_renderer.format == "json":
            return None  # disables pagination
        return super().paginate_queryset(queryset)


router.register(r"feedback", FeednackViewSet, basename="feedback")
router.register(r"modules", ModuleViewSet)
router.register(r"tests", TestViewSet)
router.register(r"test_attempts", TestAttemptViewSet)
router.register(r"test_scores", TestScoreViewSet)
schema_view = get_schema_view(title="VITALs API")
