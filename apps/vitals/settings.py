# -*- coding: utf-8 -*-
"""Settings for the VITALs app"""

CONSTANCE_CONFIG = {
    "VITALS_WEIGHT": (2.0, "VITALs Scores weighting", float),
}

VITALS_RESULTS_MAPPING = {
    "Ok": ("Passed", "forestgreen"),
    "Started": ("In Progress", "blue"),
    "Finished": ("Not Passed", "red"),
}
