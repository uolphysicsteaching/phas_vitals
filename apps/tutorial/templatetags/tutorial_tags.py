# -*- coding: utf-8 -*-
"""Custom tags for tutorial pages."""

# Django imports
from django import template
from django.utils.html import format_html

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
def engagement(student, semester, cohort):
    """Build an engagement entry for a givent student and semester."""
    if hasattr(student, "engagement_session"):
        data = student.engagement_session(cohort, semester)
    else:
        data = {}
    out = ""
    for k, v in data.items():
        out += (
            f"<td class='session_score' id='session_{student.pk}_{k}'"
            + """ headers='session_{student.tutorial_group.first().pk}_{k}'>
            {v}<br/>{lab_data[k]}
        </td>"""
        )
    return format_html(out)


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
    if score is None or score == "":
        ret = " - "
    elif int(score) < 0:
        ret = '<img src="/static/admin/img/icon-yes.svg" Alt="Authorised "Absence"/>'
    elif int(score) == 0:
        ret = '<img src="/static/admin/img/icon-no.svg" Alt="Unauthorised Absence"/>'
    else:
        ret = f"{int(score)}"

    return format_html(ret)
