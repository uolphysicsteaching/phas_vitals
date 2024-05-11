# -*- coding: utf-8 -*-
"""Custom http classes for phas-vitals."""

# Python imports
import base64 as b64
from io import BytesIO

# Django imports
from django.http import HttpResponse

# external imports
import matplotlib.pyplot as plt


def svg_data(plot=None, base64=False):
    """Save a Matplotlib figure to an an svg string.

    Keyword Arguments:
        plot (Figure, Axes, int, str or None):
            If Axes instance, get the corresponding Figure. If None, get the figure for the current axes. If int or str
            look in the list of figure numbers or labels.
            Figure to save to string.

    Return:
        (str):
            svg data in a string.
    """
    if plot is None:
        plot = plt.gca()
    if isinstance(plot, plt.Axes):
        plot = plot.figure
    if isinstance(plot, (str, int)) and (plot in plt.get_fignums() or plot in plt.get_figlabels()):
        plot = plt.figure(plot)

    if not isinstance(plot, plt.Figure):
        raise TypeError(f"plot should be a Figure, Axes or None not a {type(plot)}")

    buffer = BytesIO()
    plot.tight_layout()
    plot.savefig(buffer, format="svg")
    buffer.seek(0)
    if base64:
        return f"data:image/svg+xml;base64,{b64.encodebytes(buffer.read()).decode()}"
    return buffer.read().decode()


class SVGResponse(HttpResponse):
    """Represent a HTTP response with a Content-Type of 'image/svg+xml'.

    This subclass of `django.http.HttpResponse` will remove most of the
    necessary boilerplate in returning SVG responses from views. The plot
    to be sent is passed in as the only positional argument, and the
    other keyword arguments are as usual for `HttpResponse.
    """

    def __init__(self, plot=None, **kwargs):
        """Construct the HttpResonse subclass."""
        kwargs["content"] = svg_data(plot)

        kwargs.setdefault("content_type", "image/svg+xml")
        super(SVGResponse, self).__init__(**kwargs)
