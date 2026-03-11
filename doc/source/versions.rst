.. _label-versions:

Changelog
=========

1.0 (2024/25)
-------------

Initial release supporting the 2024/25 Physics and Astronomy Programmes at the
University of Leeds.

* Custom ``Account`` user model with academic metadata.
* Minerva (Blackboard Ultra) gradebook CSV import for tests and attempt histories.
* VITAL (Verifiable Indicators of Threshold Ability and Learning) definitions and
  automated pass/fail computation.
* Tutorial group management, attendance recording, and engagement scoring.
* Excel mark-sheet and performance spreadsheet generation.
* Baton-themed Django admin with custom navigation menus.
* HTMX-powered interactive UI components.
* Django REST Framework API with API-key authentication.
* Integration with University of Leeds ADFS single sign-on (``django-auth-adfs``).
* Celery background task processing with ``django-celery-results`` and
  ``django-celery-beat``.
* Whitenoise for static file serving.
* Sitetree-based navigation with group-level access control.
