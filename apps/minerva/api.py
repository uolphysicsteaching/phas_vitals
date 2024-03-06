# -*- coding: utf-8 -*-
"""Django REST framework API file."""

# Django imports

# external imports
from rest_framework import serializers, viewsets

# app imports
from phas_vitals.api import router

# app imports
from .models import Module, Test, Test_Attempt, Test_Score

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


router.register(r"modules", ModuleViewSet)
router.register(r"tests", TestViewSet)
router.register(r"test_attempts", TestAttemptViewSet)
router.register(r"test_scores", TestScoreViewSet)
