# -*- coding: utf-8 -*-
"""Settings for tutorial app."""

CONSTANCE_CONFIG = {
    "ENGAGEMENT_TC": (5, "Time constant of engagement score (ttorials)", int),
    "TUTORIALS_WEIGHT": (1.0, "Tutorial engagement Scores weighting", float),
}

TUTORIAL_MARKS = [
    (-1.0, "Allowed\nAbsence"),
    (0.0, "Unexplained\nAbsence"),
    (1.0, "Present\nlimited engagement"),
    (2.0, "Present\ngood engagement"),
    (3.0, "Present\noutstanding\nengagement"),
]

SEMESTERS = [(0, "Out of Semester"), (1, "Semester 1"), (2, "Semester 2"), (3, "Semesters 1+2")]
