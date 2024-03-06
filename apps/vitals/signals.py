# -*- coding: utf-8 -*-
"""Signal functions for the VITALs app."""
# Django imports
from django.dispatch import receiver

# external imports
from minerva.models import Test_Score
from minerva.signals import test_passed


@receiver(test_passed, sender=Test_Score)
def handle_test_passed(sender, test, **kargs):
    """For each vital that uses this test, check whether a vital is passed and update as necessary."""
    for vm in test.test.vitals_mappings.all().prefetch_related("vital"):  # For each vital that this test could pass
        vm.vital.check_vital(test.user)
