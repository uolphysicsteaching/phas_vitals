# -*- coding: utf-8 -*-
"""Custom tags for tutorial pages."""

# Django imports
from django import template
from django.utils.html import format_html, format_html_join

# external imports
import numpy as np
from matplotlib.cm import RdYlGn as color, jet
from matplotlib.colors import ColorConverter

# app imports
from ..models import contrast

register = template.Library()


@register.filter
def ScoreToColor(score):
    """Return a css colour code for a numerical score."""
    try:
        score = (float(score) / 100.0) ** 0.25
    except (ValueError, TypeError):
        return "#FFFFFF"
    rgb = ColorConverter.to_rgb(jet(score))
    rgb = [int(255 * x) for x in rgb]
    rgb = tuple(rgb)
    return "#{0:02X}{1:02X}{2:02X}".format(*rgb)


@register.filter
def colour(value):
    """Convert a value to a css colour."""
    if not isinstance(value, (float, int)) or np.isnan(value):
        return "#ffffff"
    value = (1 - (value / 100.0)) ** 2
    rgb = ColorConverter.to_rgb(color(value))
    rgb = [int(255 * x) for x in rgb]
    rgb = tuple(rgb)
    return "#{0:02X}{1:02X}{2:02X}".format(*rgb)


@register.filter
def rev_colour(value):
    """Convert a value to colour, but on an inverse scale."""
    if not isinstance(value, (float, int)) or np.isnan(value):
        return "#ffffff"
    value = max((value - 40) / 60, 0) ** 0.25
    rgb = ColorConverter.to_rgb(color(value))
    rgb = [int(255 * x) for x in rgb]
    rgb = tuple(rgb)
    return "#{0:02X}{1:02X}{2:02X}".format(*rgb)


@register.filter
def comp_colour(value, formula="linear"):
    """Find a complementary colour."""
    if isinstance(value, str):
        return contrast(value)
    if not isinstance(value, (float, int)) or np.isnan(value):
        return "#ffffff" if formula == "linear" else "#ffffff"
    if formula == "quad":
        value = (1 - (float(value) / 100.0)) ** 2
    else:
        value = (float(value) / 100.0) ** 0.25
    r, g, b = ColorConverter.to_rgb(color(value))
    if formula == "linear":
        r = 1 - r
        g = 1 - g
        b = 1 - b
    if np.mean([r, g, b]) > 0.5:
        return "#000000"
    else:
        return "#ffffff"


@register.simple_tag
def engagement(student, semester, cohort, sessions):
    """Build an engagement entry for a student and the displayed sessions."""
    if hasattr(student, "engagement_session"):
        data = student.engagement_session(cohort, semester, sessions=sessions)
    else:
        data = {}
    cells = []
    group = student.tutorial_group.first()
    for session in sessions:
        if session.pk in data:
            cells.append(
                format_html(
                    "<td class='session_score' id='session_{student}_{session}'"
                    + """ headers='session_{group}_{session}'>
                {value}<br/>
            </td>""",
                    student=student.pk,
                    session=session.pk,
                    value=data[session.pk],
                    group=group.pk,
                )
            )
        else:
            cells.append(
                format_html('<td headers="session_{group}_{session}">&nbsp;</td>', group=group.pk, session=session.pk)
            )
    return format_html_join("", "{}", ((cell,) for cell in cells))


@register.simple_tag
def absence(student, semester, cohort, typ):
    """Build an absence entry for a student for a semester."""
    if hasattr(student, "absence"):
        if typ == "Tutorial":
            score = student.absence(cohort, semester)
        else:
            score = student.lab_absence(cohort, semester)
        col = colour(score)
        tcol = comp_colour(score, formula="quad")
        out = f"<span style='background: {col}; color: {tcol}; display:block; width:100%;'>{score:.1f}%</span>"
    else:
        out = "<td>&nbsp;</td>"
    return format_html(out)


@register.filter
def score_display(score):
    """Build an entry for a score."""
    score_imgs = [
        {"src": "/static/admin/img/icon-yes.svg", "alt": "Authorised Absence"},
        {"akt": "/static/admin/img/icon-no.svg", "alt": "Unauthorised Absence"},
        {"alt:": "/static/img/bronze_start.svg", "alt": "Limited Engagement"},
        {"alt:": "/static/img/silver_start.svg", "alt": "Good Engagement"},
        {"alt:": "/static/img/gold_start.svg", "alt": "Outstanding Engagement"},
    ]
    if score is None or score == "":
        ret = " - "
    else:
        score = int(score) + 1
        attrs = " ".join([f'{k}="{val}' for k, val in score_imgs[score].items()])
        ret = f"<img {attrs} />"
    return format_html(ret)
