# -*- coding: utf-8 -*-
"""
Created on Sun Feb  4 16:36:47 2024

@author: phygbu
"""
# Django imports
from django.dispatch import receiver

# external imports
from minerva.models import Test_Score
from minerva.signals import test_passed


@receiver(test_passed, sender=Test_Score)
def handle_test_passed(sender, test, **kargs):
    """For each vital that uses this test, check whether a vital is passed and update as necessary."""
    for vital_test_map in test.test.vitals_mappings.all():  # For each vital that this test could pass
        if vital_test_map.sufficient:  # Can pass the VITAL now if the mapping indicates the test is sufficient
            vital_test_map.vital.passed(user=test.user)
        if vital_test_map.necessary:  # Only passes if all the other necessary tests pass
            for test_mapping in vital_test_map.vital.tests_mappings.filter(necessary=True):  # Check all the tests
                if test_mapping.test.results.filter(user=test.user, passed=True).count() < 1:  # if no passed records
                    break  # Dump from the loop
            else:  # alll necessary tests passed
                vital_test_map.vital.passed(user=test.user)
