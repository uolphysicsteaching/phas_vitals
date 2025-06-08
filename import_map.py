# -*- coding: utf-8 -*-
"""Import the Excel spreadsheet map of VITLALs-tests mapping as exported from the Module admin action."""

# Python imports
from pprint import pprint

# Django imports
from django.core.exceptions import ObjectDoesNotExist

# external imports
import numpy as np
import pandas as pd
from minerva.models import Test
from vitals.models import VITAL, VITAL_Test_Map

filename = "VITALs_map_PHAS1000.xlsx"

df = pd.read_excel(filename).set_index("VITAL")
col_map = {}
for col in df.columns:
    try:
        col_map[col] = Test.objects.get(name=col)
    except Test.DoesNotExist:
        col_map[col] = None

pprint(col_map)

for name, row in df.iterrows():
    try:
        vital = VITAL.objects.get(VITAL_ID=name.split("\n")[0].strip())
    except VITAL.DoesNotExist:
        continue
    tests = []
    for col, value in row.items():
        if value == "X":
            tests.append(col_map[col].pk)
    to_remove = vital.tests_mappings.exclude(test__pk__in=tests)
    to_add = Test.objects.filter(pk__in=tests).exclude(vitals_mappings__vital=vital)
    print(f"{vital.VITAL_ID}\n\tadd : {to_add}\n\tremove: {to_remove}")
    if to_remove:
        to_remove.delete()
    for new_test in to_add:
        vm, _ = VITAL_Test_Map.objects.get_or_create(vital=vital, test=new_test, sufficient=True)
