#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Support various tutorial related views with django-tabvles2 subclasses."""
# Django imports
from django.utils.html import format_html

# external imports
from django_tables2.columns import Column
from django_tables2.tables import Table


class BaseTable(Table):
    """Base class for tables about students."""

    class Meta:
        attrs = {"width": "100%"}

    student = Column()
    tutor = Column()


class BaseMarkTable(BaseTable):
    """Base class for tables about student marks."""

    submitted = Column()
    similarity = Column()
    downloaded = Column()
    marked = Column()


class MarkColumn(Column):
    """Column type that can display marks or glyphs."""

    def __init__(self, **kargs):
        """Construct the column instance with default attrs."""
        attrs = kargs.pop("attrs", {})
        attrs.update({"th": {"class": "vertical"}})
        kargs["attrs"] = attrs
        super(MarkColumn, self).__init__(**kargs)

    def render(self, value):
        """Produce html for the cell value."""
        if isinstance(value, bool) and value:
            ret = format_html("<img src='/static/admin/img/icon-yes.svg' alt='Yes'/>")
        elif isinstance(value, bool) and not value:
            ret = format_html("<img src='/static/admin/img/icon-no.svg' alt='No'/>")
        elif isinstance(value, (float, int)):
            ret = "{}%".format(value)
        elif isinstance(value, str):
            ret = format_html(value)
        elif value is None:
            ret = format_html("&nbsp;")
        else:
            ret = str(type(value))
        return ret
