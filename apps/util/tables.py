# -*- coding: utf-8 -*-
"""Common django-tables classes."""
# external imports
from django_tables2.columns import Column
from django_tables2.tables import Table


class BaseTable(Table):
    """Provides a table with columns for student name, number, programme and status code as per marksheets."""

    class Meta:
        orderable = False
        template_name = "util/table.html"

    student = Column(orderable=False, attrs={"td": {"class": "student"}})
    number = Column(orderable=False, attrs={"td": {"class": "SID"}})
    programme = Column(orderable=False, attrs={"td": {"class": "Prgoramme"}})
    status = Column(attrs={"th": {"class": "vertical"}, "td": {"class": "status"}}, orderable=False)
