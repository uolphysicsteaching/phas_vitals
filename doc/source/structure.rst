.. _label-project-structure:

Project Structure
=================

Top-level Layout
----------------

::

    phas_vitals/                        <- project root
    ├── apps/                           <- custom Django applications
    │   ├── accounts/
    │   ├── htmx_views/
    │   ├── minerva/
    │   ├── psrb/
    │   ├── tutorial/
    │   ├── util/
    │   └── vitals/
    ├── configs/                        <- deployment configuration samples
    │   ├── apache2_vhost.sample
    │   ├── Makefile.sample
    │   └── README
    ├── doc/                            <- Sphinx documentation
    │   ├── Makefile
    │   └── source/
    ├── fixtures/                       <- initial data fixtures
    ├── phas_vitals/                    <- Django project package
    │   ├── settings/
    │   │   ├── common.py
    │   │   ├── development.py
    │   │   ├── i18n.py
    │   │   ├── production.py
    │   │   └── test.py
    │   ├── fixtures/                   <- project-level fixture files
    │   ├── urls.py
    │   ├── views.py
    │   ├── api.py
    │   └── wsgi.py
    ├── requirements/                   <- pip requirement files
    ├── run/                            <- runtime files (not in version control)
    │   ├── media/
    │   ├── static/
    │   └── SECRET.key
    ├── static/                         <- project-wide static assets
    │   ├── css/
    │   └── img/
    ├── templates/                      <- project-wide templates
    │   ├── base.html
    │   ├── home.html
    │   ├── core/
    │   ├── errors/
    │   ├── flatpages/
    │   └── registration/
    ├── conftest.py
    ├── manage.py
    ├── pytest.ini
    ├── README.rst
    └── tox.ini


Django Project Package (``phas_vitals/``)
-----------------------------------------

::

    phas_vitals/
    ├── settings/
    │   ├── common.py       <- shared settings for all environments
    │   ├── development.py  <- development overrides (imports secrets.py)
    │   ├── i18n.py         <- internationalisation settings
    │   ├── production.py   <- production security settings
    │   └── test.py         <- test-suite settings
    ├── urls.py             <- root URL configuration
    ├── views.py            <- root views and error handlers
    ├── api.py              <- Django REST Framework router
    └── wsgi.py             <- WSGI entry point

``phas_vitals/settings/``
    Settings are split across several files. See :ref:`label-project-settings` for details.

``phas_vitals/urls.py``
    Root URL configuration. Mounts each application's URL module and third-party
    URL namespaces (admin, OAuth2, TinyMCE, AJAX select, etc.).

``phas_vitals/views.py``
    Provides the ``HomeView`` landing page and custom 403/404/500 error handlers.

``phas_vitals/api.py``
    Configures the Django REST Framework router and registers API viewsets from
    each application.


apps/
-----

All custom Django applications live under ``apps/``. The settings module
automatically discovers any sub-directory that contains a ``models.py`` file and
adds it to ``INSTALLED_APPS``.


accounts app
^^^^^^^^^^^^

**Purpose:** User authentication, account management, and academic organisation.

Models
""""""

``Cohort``
    Academic cohort identified by a short name (e.g. ``202425`` for 2024/25).

``School``
    Academic school with a name, short code, module-code prefixes, and managers.

``Programme``
    Degree programme with a code, name, owning school, and level indicator.

``Year``
    Year or level of study (undergraduate or postgraduate taught).

``Account``
    Custom user model extending ``AbstractUser``. Adds a student number,
    title, programme, school, year, given name, registration status, lab section,
    VITAL override/update flags, and an activity score.

``Section``
    Lab group used to manage Gradescope rosters, with a name, group code, and
    self-enrolment flag.

``TermDate``
    Maps calendar dates to semester weeks for a given cohort.

``AccountGroup``
    Proxy model exposing Django ``Group`` objects through a dedicated admin page.

Views
"""""

``ChangePasswordView``
    Allow users to update their own password.

``TutorGroupEmailsView``
    Compose and send e-mails to an entire tutorial group.

``StudentSummaryView``
    Display a student's full academic profile.

``StudentSummaryPageView``
    HTMX-enabled tabbed pages within the student summary.

``CohortFilterActivityScoresView``
    List activity scores filtered by cohort.

``CohortFilterActivityScoresExportView``
    Export cohort activity scores to an XLSX spreadsheet.

``CohortScoresOverview``
    Visualisation of cohort test-score distributions.

``CohortProgressionOverview``
    Visualisation of score progression over time.

``StudentRecordView``
    Staff lookup for individual student records.

``DeactivateStudentView``
    Toggle a student's active/inactive status.

``AwardVITALView``
    Manually override a student's VITAL award.

``StudentAutocomplete``, ``StaffAutocomplete``
    DAL (django-autocomplete-light) autocomplete endpoints.

URLs (prefix: ``accounts/``)
"""""""""""""""""""""""""""""

* ``tutor_email/``
* ``detail/<number>/``
* ``detail/<number>/<category>/``
* ``change-password/``
* ``tools/student_list/``
* ``tools/student_list/xlsx/``
* ``tools/toggle_active/``
* ``tools/toggle_vital/``
* ``tools/scores_summary/``
* ``tools/scores_progression/``
* ``tools/student_dashboard/``
* ``student_lookup/``
* ``staff_lookup/``


minerva app
^^^^^^^^^^^

**Purpose:** Integration with Blackboard Ultra (Minerva); test and gradebook management.

Models
""""""

``Module``
    Represents a Minerva course. Stores a UUID, course ID, module code, name,
    level, cohort, semester, school, module leader and team, and a many-to-many
    relationship to enrolled students via ``ModuleEnrollment``.

``TestCategory``
    Groups tests within a module (e.g. *Homework*, *Lab Experiments*). Supports
    ordering, dashboard visibility, and a regex pattern for matching column names.

``StatusCode``
    Banner registration status codes (e.g. RE, WD) with validity and resit flags.

``ModuleEnrollment``
    Links a student to a module with an associated status code and Minerva user ID.

``SummaryScore``
    Aggregated score per student per test category within a module, with a JSON
    data blob for additional statistics.

``Test``
    An individual test or assignment. Stores the Minerva test ID, name, module,
    category, pass mark, release date, due date, recommended date, attempt limit,
    and flags for suppressing numerical scores and ignoring zero or waiting grades.

``GradebookColumn``
    A Minerva gradebook column that may or may not be linked to a ``Test``.
    Tracks visibility, include-in-calculations, and priority.

``Test_Score``
    A student's overall standing on a test: grade, number of attempts, last attempt
    date, pass status, and pass date.

``Test_Attempt``
    An individual attempt at a test, recording the attempt number, grade,
    submission date, and status.

Views
"""""

``ImportTestsView``, ``StreamingImportTestsView``
    Upload and process a Minerva Full Gradebook CSV to create ``Test`` objects.

``ImportTestHistoryView``, ``StreamingImportTestsHistoryView``
    Upload and process a Minerva Gradebook History CSV to record test scores and
    attempts.

``ShowTestResults``, ``ShowAllTestResultsViiew``, ``ShowTutorTestResultsViiew``
    Display test results with filtering. The all-results view is restricted to
    superusers; the tutor view shows only the tutor's own students.

``GenerateModuleMarksheetView``
    Generate and download an Excel mark-sheet for a module.

``StudentPerformanceSpreadsheetView``
    Generate and download a per-student performance spreadsheet.

``TestDetailView``
    Detailed information page for a single test.

``TestResultsBarChartView``
    Bar-chart visualisation of score distributions for a test.

``ModuleAutocomplete``, ``TestAutocomplete``
    DAL autocomplete endpoints for module and test selection.

URLs (prefix: ``minerva/``)
""""""""""""""""""""""""""""

* ``import_tests/``
* ``import_tests_stream/``
* ``import_history/``
* ``import_history_stream/``
* ``test_view/``
* ``test_barchart/``
* ``generate_marksheet/``
* ``generate_performance_spreadsheet/``
* ``detail/<pk>/``
* ``dal_modules/``
* ``dal_tests/``


vitals app
^^^^^^^^^^

**Purpose:** VITAL definitions, test-to-VITAL mappings, and outcome tracking.

Models
""""""

``VITAL``
    A learning outcome within a module. Has a name (unique per module), VITAL ID,
    description, owning module, and many-to-many relationships to tests (via
    ``VITAL_Test_Map``) and students (via ``VITAL_Result``).

``VITAL_Test_Map``
    Maps a test to a VITAL with configurable pass logic: a test can be *necessary*
    (all necessary tests must pass) and/or *sufficient* (passing one suffices). A
    required fraction and condition (``"pass"`` or ``"attempt"``) can also be set.

``VITAL_Result``
    Records whether a specific student has passed a VITAL and the date of passing.

Views
"""""

``ShowVitralResultsView``
    Entry-point view that redirects to the appropriate results view based on the
    user's role (student, tutor, or administrator).

``ShowAllVitalResultsView``
    Full VITAL results table; restricted to superusers.

``ShowTutorVitalResultsView``
    VITAL results for a tutor's own students.

``VitalDetailView``
    Detailed information page for a single VITAL.

``VITALAutocomplete``
    DAL autocomplete endpoint for VITAL selection.

URLs (prefix: ``vitals/``)
"""""""""""""""""""""""""""

* ``vitals_view/``
* ``detail/<pk>/``
* ``VITALlookup/``


tutorial app
^^^^^^^^^^^^

**Purpose:** Tutorial group management, attendance recording, engagement monitoring,
and meeting notes.

Models
""""""

``Tutorial``
    A tutorial group consisting of a tutor, a cohort, a group code, and a
    many-to-many relationship to students via ``TutorialAssignment``.

``TutorialAssignment``
    One-to-one link between a student and their tutorial group.

``Session``
    A teaching session (lecture, lab, or tutorial) with a name, semester, cohort,
    associated module, week number, and start/end dates.

``SessionType``
    Classification of sessions (e.g. Tutorial, Lab).

``Attendance``
    Records a student's attendance at a session with a score.

``Meeting``
    A record of a tutorial meeting, including date, notes, attendees, and audit
    fields for creation and modification.

``MeetingAttendance``
    Links a student to a meeting record with a present/absent flag.

Views
"""""

*Admin views* (``views/admin.py``):

``AdminDashboardView``
    Overview dashboard for staff.

``MeetingsSummary``
    Summary table of tutorial meetings across cohorts.

``StudentMarkingSummary``
    Per-student marking summary for staff review.

``AcademicIntegrityUpload``
    Upload academic integrity records.

*Engagement views* (``views/engagement.py``):

``TutorStudentEngagementSummary``, ``AdminEngagementSummaryView``
    Display engagement scores for tutors and administrators respectively.

``SubmitStudentEngagementView``, ``AdminSubmitStudentEngagementView``
    Submit engagement scores for students.

``AdminResultStudentEngagementView``
    View submitted engagement results.

``ShowEngagementView``
    Entry-point view that redirects based on role.

``LabAttendanceUpload``
    Upload lab attendance data from a CSV file.

*Group management views* (``views/groups.py``):

``AssignTutorGroupsView``
    Assign students to tutorial groups for a cohort.

``ToggleTutorialAssignmentField``
    Toggle individual fields on a student's tutorial assignment record.

``ToggleMeeting``
    Toggle the presence of a student at a meeting.

URLs (prefix: ``tutorial/``)
"""""""""""""""""""""""""""""

* ``admin/assign/<cohort>/``, ``admin/assign/``
* ``admin/ai_upload/``
* ``admin/dashboard/<cohort>/``, ``admin/dashboard/``
* ``admin/meetings_summary/<cohort>/``, ``admin/meetings_summary/``
* ``admin/lab_attendance/``
* ``admin/engagement/…``
* ``engagement/submit/<session>/``
* ``engagement/admin_submit/session_<student>_<session>/``
* ``engagement/admin_result/session_<student>_<session>/``
* ``engagement_view/``
* ``engagement_view/<semester>/<cohort>/``
* ``engagement_view/<semester>/<cohort>/<code>/``
* ``marking/toggle/<user>/<component>/``
* ``marking/toggle_meeting/<username>/<slug>/``
* ``marking_view/``, ``marking_view/<issid>/``


util app
^^^^^^^^

**Purpose:** Utility functions, data exports/imports, and API key management.

Models
""""""

``APIKey``
    A DRF authentication key with an active flag, creation date, and comment field.

``GroupedTree``
    Navigation menu tree (extends django-sitetree).

``GroupedTreeItem``
    Navigation menu item with access restrictions by group membership and
    staff/superuser flags.

Views
"""""

``SuperuserTemplateView``
    Superuser-only tools page.

``StaffUserTemplateView``
    Staff tools page.

``RedirectView``
    Smart redirect that routes users to an appropriate page based on their role.

``FormListView``
    Generic list view with an accompanying form.

``MultiFormsView``, ``ProcessMultipleFormsView``
    Handle pages with multiple independent forms.

URLs (prefix: ``util/``)
"""""""""""""""""""""""""

* ``tools/``
* ``data/``
* ``gradebook/``


htmx_views app
^^^^^^^^^^^^^^

**Purpose:** HTMX-based dynamic view endpoints for interactive UI components.

Models
""""""

None.

Views
"""""

``LinkedSelectEndpointView``
    HTMX endpoint that powers linked (chained) dropdown select elements.

URLs (prefix: ``htmx_views/``)
"""""""""""""""""""""""""""""""

* ``select/<lookup_channel>/``


psrb app
^^^^^^^^

**Purpose:** Placeholder for future PSRB (Professional Standards Reference Body) support.

Models
""""""

None.

Views
"""""

None.


Root URL Configuration
----------------------

The root ``phas_vitals/urls.py`` mounts the following URL namespaces:

============================================ =========================================
URL prefix                                   Target
============================================ =========================================
``/``                                        ``HomeView`` (landing page)
``/riaradh/``                                Django admin (Baton theme)
``/api/``                                    DRF router (REST API)
``/api-auth/``                               DRF session-auth views
``/baton/``                                  Baton admin extras
``/isteach/``                                Login view
``/imigh/``                                  HTMX-aware logout view
``/o/``                                      OAuth2 provider
``/oauth2/``                                 ADFS OAuth2 authentication
``/tinymce/``                                TinyMCE editor endpoints
``/ajax_select/``                            AJAX autocomplete
``/chaining/``                               django-smart-selects chained selects
``/accounts/``                               accounts app URLs
``/minerva/``                                minerva app URLs
``/vitals/``                                 vitals app URLs
``/tutorial/``                               tutorial app URLs
``/util/``                                   util app URLs
``/htmx_views/``                             htmx_views app URLs
``/psrb/``                                   psrb app URLs
============================================ =========================================

Custom error handlers: ``handler403``, ``handler404``, and ``handler500`` are
provided via views in ``phas_vitals/views.py``.


configs/
--------

::

    phas_vitals/
    ├── configs/
    │   ├── apache2_vhost.sample    <- sample Apache2 virtual-host configuration
    │   ├── Makefile.sample         <- sample Makefile for server management
    │   └── README

The ``.gitignore`` in this directory prevents real (non-sample) configuration
files from being committed to version control. See :ref:`label-apache2-vhost` for
a description of the sample virtual-host file.


run/
----

::

    phas_vitals/
    └── run/
        ├── media/      <- user-uploaded files (MEDIA_ROOT)
        ├── static/     <- collected static files (STATIC_ROOT)
        ├── logs/       <- application log files
        └── SECRET.key  <- Django SECRET_KEY (auto-generated)

This directory is excluded from version control. It contains runtime artefacts
that may hold sensitive or ephemeral data.


static/ and templates/
-----------------------

::

    phas_vitals/
    ├── static/
    │   ├── css/
    │   └── img/
    └── templates/
        ├── base.html
        ├── home.html
        ├── core/
        │   └── login.html
        ├── errors/
        │   ├── 403View.html
        │   ├── 404View.html
        │   └── 500View.html
        ├── flatpages/
        │   └── default.html
        └── registration/
            └── login.html

``static/``
    Project-wide static assets (CSS stylesheets, images, JavaScript libraries).
    The ``STATICFILES_DIRS`` setting includes this directory. Static files
    contributed by each app are stored inside the respective app's ``static/``
    sub-directory. All assets are collected into ``run/static/`` by
    ``collectstatic``.

``templates/``
    Project-wide templates. ``APP_DIRS = True`` causes Django to also look inside
    each app's ``templates/`` sub-directory. The ``TEMPLATES`` setting's ``DIRS``
    list points to this directory.
