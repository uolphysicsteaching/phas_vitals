.. PHAS VITALs documentation master file.

PHAS VITALs
===========

**PHAS VITALs** is a Django-based web application designed to support the Physics and Astronomy
Programmes at the University of Leeds (2024/25 onwards). Its overall task is to collect test scores
from the Blackboard Ultra (Minerva) gradebook, compare scores against per-test pass marks, and map the
pass/fail status of individual tests to a student's *Verifiable Indicators of Threshold Ability and
Learning* – **VITALs**. The application also produces mark-sheets for recording student progress.

The repository is public (and does not contain any personal data or secrets). See
`https://github.com/uolphysicsteaching/phas_vitals <https://github.com/uolphysicsteaching/phas_vitals>`_.

Notable Features
----------------

* Imports test scores and attempt histories from Minerva (Blackboard Ultra) gradebook CSV exports.
* Automatically computes VITAL pass/fail status from test results.
* Generates Excel mark-sheets and performance spreadsheets.
* Role-based views for students, tutors, and administrators.
* Tutorial-group management with attendance and engagement tracking.
* HTMX-powered interactive UI elements.
* REST API for programmatic access.
* Integration with University of Leeds ADFS (single sign-on) and OAuth2.
* Celery-based background task processing.

Contents
--------

.. toctree::
    :maxdepth: 2

    quickstart
    structure
    settings
    apache2_vhost
    versions
