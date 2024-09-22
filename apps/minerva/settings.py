# -*- coding: utf-8 -*-
"""Custom settings for app."""

# Python imports
from datetime import datetime

# external imports
from pytz import UTC

CONSTANCE_CONFIG = {
    "SUBJECT_PREFIX": ("PHAS", "Module Subject code prefix"),
    "TESTS_WEIGHT": (1.0, "Test Scores weighting", float),
    "CODING_WEIGHT": (1.5, "Code Tasks Scores weighting", float),
    "LABS_WEIGHT": (1.5, "Lab Scores weighting", float),
    "LAST_MINERVA_UPDATE": (datetime.now(tz=UTC), "Last update from Minerva", "custdatetime"),
    "LAB_PATTERN": (r"\W+\s+\-\s+(?P<name>Expt\..*)", "Regular expression pattern to match Lab columns", str),
    "HOMEWORK_PATTERN": (r"(?P<name>Week\s+\d+\s+Homework", "Regular expression to Match Homework columns", str),
    "CODE_PATTERN": (r"Computing\s+-\s+(?P<name>.*)", "Regular expression pattern to match coide task columns", str),
    "TUTORIAL_MODULE": ("PHAS1000", "Module code for tutorial sessions", str),
}

TESTS_ATTEMPTS_PROFILE = {
    "Ok": {
        "Passed\nfirst time": (1, "forestgreen"),
        "Passed in\n2 or 3 attempts": (3, "mediumseagreen"),
        "Passed in\nmoire than 3 attempts": (999, "springgreen"),
    },
    "Overdue": {
        "Not passed\n1 attempt": (1, "lightcoral"),
        "Not passed\nless than 3 attempts": (3, "tomato"),
        "Not passed\nmore than 3 attempts": (999, "red"),
    },
    "Missing": {"Not attempted": (-1, "grey")},
    "Not Started": {"Attempted early": (-1, "lightgrey")},
    "Finished": {"Failed": (-1, "darkred")},
    "Released": {
        "In progress\n1 attempt": (1, "lightsteelblue"),
        "In progress\nless than 3 attempts": (3, "steelblue"),
        "In progress\nmore than 3 attempts": (999, "blue"),
    },
}
