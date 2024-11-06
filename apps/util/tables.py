# -*- coding: utf-8 -*-
"""Common django-tables classes."""
# Django imports
from django.utils.html import format_html

# external imports
from django_tables2.columns import Column
from django_tables2.tables import Table


class StudentColumn(Column):
    """Handles displaying test result information."""

    def __init__(self, **kargs):
        """Mark the header table to user vertical oriented text."""
        attrs = {"td": {"class": "student"}}
        attrs.update(kargs.pop("attrs", {}))
        kargs["attrs"] = attrs
        kargs["orderable"] = kargs.get("orderable", False)
        super().__init__(**kargs)

    def render(self, value):
        """Render the cell values."""
        ret = f'<div id="{value.number}" style="background-color: {value.activity_colour}">{value.display_name}</div>'
        return format_html(ret)


class BaseTable(Table):
    """Provides a table with columns for student name, number, programme and status code as per marksheets."""

    class Meta:
        orderable = False
        template_name = "util/table.html"

    student = StudentColumn()
    number = Column(orderable=False, attrs={"td": {"class": "SID"}})
    programme = Column(orderable=False, attrs={"td": {"class": "Prgoramme"}})
    status = Column(attrs={"th": {"class": "vertical"}, "td": {"class": "status"}}, orderable=False)
