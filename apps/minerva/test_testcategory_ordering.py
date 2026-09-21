"""Tests for test-category ordering."""

# Python imports
from importlib import import_module
from types import SimpleNamespace

# Django imports
from django.apps import apps
from django.db import connection

# external imports
import pytest

# app imports
from .models import TestCategory as CategoryModel


@pytest.mark.django_db
@pytest.mark.unit
def test_new_categories_receive_unique_positive_order_values(sample_module):
    """Assign sortable positions to categories created outside the admin."""
    first = CategoryModel.objects.create(module=sample_module, text="First", category_id="first")
    second = CategoryModel.objects.create(module=sample_module, text="Second", category_id="second")

    assert first.order > 0
    assert second.order == first.order + 1


@pytest.mark.django_db
@pytest.mark.unit
def test_order_migration_replaces_legacy_duplicate_zero_values(sample_module):
    """Give legacy categories valid, deterministic positions for the sortable admin."""
    CategoryModel.objects.bulk_create(
        [
            CategoryModel(module=sample_module, text="First", category_id="first"),
            CategoryModel(module=sample_module, text="Second", category_id="second"),
            CategoryModel(module=sample_module, text="Third", category_id="third", order=4),
        ]
    )
    migration = import_module("apps.minerva.migrations.0042_normalise_testcategory_order")

    migration.normalise_testcategory_order(apps, SimpleNamespace(connection=connection))

    categories = CategoryModel.objects.order_by("pk")
    assert list(categories.values_list("order", flat=True)) == [1, 2, 3]


@pytest.mark.django_db
@pytest.mark.unit
def test_saving_category_fields_preserves_a_reordered_position(sample_module):
    """Keep drag-and-drop positions when editable admin fields are subsequently saved."""
    first = CategoryModel.objects.create(module=sample_module, text="First", category_id="first")
    second = CategoryModel.objects.create(module=sample_module, text="Second", category_id="second")
    third = CategoryModel.objects.create(module=sample_module, text="Third", category_id="third")
    first.order, second.order, third.order = 3, 1, 2
    CategoryModel.objects.bulk_update([first, second, third], ["order"])

    first.in_dashboard = True
    first.save()
    first.refresh_from_db()

    assert first.order == 3
    assert list(CategoryModel.objects.values_list("category_id", flat=True)) == ["second", "third", "first"]
