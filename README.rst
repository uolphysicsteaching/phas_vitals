Physics VITALs Reporting Tool
=============================

Overview
~~~~~~~~

This Django web application supports the 2024/25 onwards Physics and Astronomy programmes at the University of Leeds.
It provides a student assessment tracking system that imports assessment information from Blackboard Ultra/Minerva,
normalises it into Django models, compares student marks with per-assessment pass marks, and maps those test outcomes to
student progress against *Verifiable Indicators of Threshold Ability and Learning* (VITALs). Staff can use the system to
monitor student progress, identify missing or overdue work, manually manage module and VITAL definitions, and export a
module marksheet for official recording.

The project is organised as a conventional Django site (``phas_vitals``) with several domain apps:

* ``accounts`` manages students, staff, schools, programmes, cohorts, sections, and authentication-facing account data.
* ``minerva`` models module gradebooks, Blackboard/Minerva columns, assessment categories, tests, attempts, test scores,
  enrolments, and summary scores.
* ``vitals`` defines VITALs and the rules that translate assessment outcomes into VITAL pass/fail records.
* ``tutorial`` tracks tutorial groups, meetings, sessions, attendance, and tutorial engagement data.
* ``util`` and ``htmx_views`` provide shared helpers, widgets, import/export utilities, API-key support, and reusable
  view behaviour.

|Codacy Badge|

.. |Codacy Badge| image:: https://app.codacy.com/project/badge/Grade/12037780d11942af86f393139869ad56
   :target: https://app.codacy.com/gh/uolphysicsteaching/phas_vitals/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade

How the student assessment tracking system works
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The system combines imported gradebook data, locally configured assessment rules, and student enrolment records. The
main workflow is:

1. Staff configure academic structures such as schools, cohorts, programmes, modules, and student accounts.
2. Module data is imported from Blackboard Ultra/Minerva JSON or gradebook exports.
3. Gradebook categories and columns are matched to local ``TestCategory`` and ``Test`` records.
4. Student membership data creates or updates ``ModuleEnrollment`` records that connect students to modules.
5. Grade data and attempt history create ``Test_Score`` and ``Test_Attempt`` records for each student/test combination.
6. Each ``Test_Score`` calculates whether the student has passed the assessment by comparing the best available attempt
   score with the test's configured passing score.
7. VITAL rules, stored as ``VITAL_Test_Map`` rows, decide whether a passed or attempted test is sufficient, necessary, or
   partially contributory towards a VITAL.
8. ``VITAL_Result`` rows record whether each student has achieved each VITAL.
9. Dashboards, detail pages, admin actions, exports, and generated spreadsheets expose the resulting progress data to
   students and staff.

Core data model
---------------

``accounts``
    ``Account`` extends Django's user model with student identifiers, programme/cohort data, school relationships,
    override flags, and convenience properties patched in by other apps. ``School``, ``Programme``, ``Cohort``, and
    ``Section`` provide the academic grouping data used to filter students and modules.

``minerva.Module``
    Represents a module marksheet/course. It stores the module code, year, semester, school, leader, team, enrolments,
    and links to imported Blackboard/Minerva JSON blobs. A module can update its categories, columns, tests,
    enrolments, grades, and attempts from imported data.

``minerva.ModuleEnrollment``
    Connects a student account to a module and stores the student's module-specific Blackboard user id and Banner status
    code. The enrolment record is the anchor for per-module summary scores.

``minerva.TestCategory``
    Represents a gradebook category such as homework, labs, coding tasks, tutorial attendance, or other dashboard
    groupings. Categories can be shown on dashboards, plotted over time, and used to match imported gradebook columns to
    tests using a regular expression.

``minerva.GradebookColumn``
    Mirrors an individual Blackboard/Minerva gradebook column. Columns can be grouped into a single logical ``Test`` so
    that one assessment may have multiple source columns.

``minerva.Test``
    Represents a logical assessment. It stores release, recommended, and due dates; the maximum and passing score; the
    category; and all linked gradebook columns. Its status is calculated from the date fields as not started, released,
    overdue, or finished.

``minerva.Test_Score``
    Links one student to one test. Saving a score recalculates the best score from attempts, sets the pass/fail flag,
    updates the related category ``SummaryScore``, and marks the student for VITAL recalculation when needed.

``minerva.Test_Attempt``
    Stores each imported attempt for a student's test entry. Saving an attempt forces the parent ``Test_Score`` to be
    recalculated.

``minerva.SummaryScore``
    Stores a per-student, per-module, per-category percentage and supporting chart data. For normal categories this is
    based on passed tests out of available/overdue tests; special category calculation methods can be supplied for
    virtual categories such as VITALs or attendance.

``vitals.VITAL``
    Represents a required learning indicator for a module. It has a name, optional VITAL id, description, module, linked
    tests, and student results.

``vitals.VITAL_Test_Map``
    Defines how a test contributes to a VITAL. A mapping can require that a student passes a test, merely attempts a
    test, satisfies a sufficient condition, satisfies a necessary condition, or accumulates enough fractional
    contribution to reach the required threshold.

``vitals.VITAL_Result``
    Records a student's pass/fail state for one VITAL, including the achievement date and optional manual lock metadata.

Assessment import and recalculation flow
----------------------------------------

The ``minerva`` app is responsible for turning Blackboard/Minerva data into local assessment records. A module's import
process can:

* update the module's gradebook categories from Minerva category JSON;
* remove stale gradebook columns;
* create or update ``GradebookColumn`` records;
* create or update ``Test`` records by matching category-specific column names;
* update module enrolments from Minerva membership data;
* build ``Test_Score`` and ``Test_Attempt`` records from imported grades and attempt data; and
* recalculate category ``SummaryScore`` values and downstream VITAL status.

The Celery tasks in ``apps/minerva/tasks.py`` wrap this process for scheduled or one-off imports. ``import_module_list``
discovers module/course JSON blobs and creates modules, while ``import_gradebook`` refreshes all modules with available
JSON data and then queues a user-wide VITAL update. ``import_one_module`` and ``rebuild_one_test`` provide narrower
maintenance operations.

VITAL award logic
-----------------

Each VITAL is linked to tests through ``VITAL_Test_Map``. When the system checks a student's VITAL status it gathers the
student's passed tests and attempted tests for that VITAL, then applies the rules in this order:

1. If any sufficient mapping is met, the VITAL is awarded.
2. If the student has no relevant test attempts, no VITAL result is written.
3. If any necessary mapping is not met, the VITAL is recorded as not passed unless the student's VITAL status is locked
   or manually overridden.
4. Otherwise, the system sums the ``required_fractrion`` values for all met mappings. If the total is at least ``1.0``,
   the VITAL is awarded; if not, it is recorded as not passed unless locked or overridden.

This means a VITAL can be configured in several ways: a single assessment may be enough to award it, every assessment in
a set may be required, or a weighted collection of attempts/passes may contribute towards the threshold.

Student and staff views
-----------------------

The URL configuration exposes a home page, Django admin, REST API routes, login/logout routes, OAuth/ADFS integration,
and app-specific URL modules. The app-specific views provide pages for module details, test details, VITAL details,
imports, exports, tutorial tracking, and HTMX-enhanced interactions. Students see assessment and VITAL status using the
calculated status fields and Bootstrap classes from the models; staff can manage data through Django admin, custom views,
and import/export resources.

Exports and reporting
---------------------

Modules can generate Physics and Astronomy marksheets from the spreadsheet template in ``run/templates``. The generated
marksheet includes VITAL pass/fail values and final codes; modules without numerical marks leave the total percentage
blank. Category summary data can also be plotted over time by scheduled tasks that save spreadsheets and animated GIFs
under ``MEDIA_ROOT/data``.

Local (Development) Setup
~~~~~~~~~~~~~~~~~~~~~~~~~~

Although the web app is designed for deployment as a WSGI application on a web server with a networked database server,
such as Gunicorn/Nginx/PostgreSQL, it is straightforward to set up and run as a local application for development or as a
private instance.

This section provides an overview of the steps to set this app up in local mode.

1. Clone or Download the Code
-----------------------------

Download and unpack the zip file of this code from GitHub: https://github.com/uolphysicsteaching/phas_vitals

The repository is public and does not contain personal data or secrets. For development, it is recommended to fork the
repository and use git.

2. Install Anaconda Python
--------------------------

If not already installed, download and install the latest version of Anaconda Python. This can be installed as an
individual user if system administrator permissions are not available.

3. Set up the conda environment
-------------------------------

The web app comes with a file that describes all the Python packages that are required to run it. The
``environment.yaml`` file specifies packages from the main Anaconda repository, the conda-forge repository, and several
packages from the maintainer's published package repository. Open an Anaconda PowerShell prompt/shell window, change
directory to the location where the code has been unpacked, and run::

    conda env create -f environment.yaml

This will take some time to execute. After it has finished, activate the new conda environment::

    conda activate django

4. Set up the database etc.
---------------------------

Before you can use the application, you need to give it a database to use. This should be configured as a file named
``secrets.py`` that is placed in the ``phas_vitals/settings/`` directory. For local operations, a SQLite database can be
set up using the following file::

    """
    Ensure that this file is in .gitignore!
    """
    from .common import *

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(PROJECT_ROOT_PATH / "run" / f"{SITE_NAME}.sql"),
        }
    }

This stores the database locally within the ``run/`` directory. The project is set up so that neither ``secrets.py`` nor
the database should be saved to GitHub by accident.

Once this is done, create the database tables, load initial values, collect static resources, and create an admin user::

    python manage.py migrate
    python manage.py loaddata phas_vitals/fixtures/sitetree.json
    python manage.py collectstatic
    python manage.py createsuperuser

In the second command the forward slash ``/`` will need to be a backslash ``\`` in Windows. ``collectstatic`` will prompt
to confirm a copy, and ``createsuperuser`` will prompt for a username, email address, and password.

There are some additional fixtures that will probably be useful::

    python manage.py loaddata phas_vitals/fixtures/statuscodes.json
    python manage.py loaddata phas_vitals/fixtures/programmes.json
    python manage.py loaddata phas_vitals/fixtures/cohort.json

These load the Banner ETS registration codes, common programmes, and some initial student cohorts.

5. Start the local server and connect to the app
------------------------------------------------

Start the web app with::

    python manage.py runserver

Finally, open a web browser and connect to http://127.0.0.1:8000

You will be able to log in with the superuser credentials set above.

6. Configure the app
--------------------

After logging in, click on the Admin menu item to access the backend of the system. Using this you can create database
entries for everything the system requires. Start by creating the following:

* Cohort objects: usually specified as a six-digit number to represent the academic year, for example ``202425``. These
  may be loaded by the ``cohort.json`` fixture above.
* Programme objects: create a programme for each degree programme that a student might be studying. These should match
  the name and code used by Banner. They may be loaded from the ``programmes.json`` fixture above.
* Student accounts: these can be imported from Banner module registration files and will create user accounts for each
  student enrolled on the system.
* Module objects: these are in the Minerva section. At least one module object is required. Key details are the module
  name and module code. The module code prefix, for example ``PHAS``, also needs to be set in the ``constance`` section.

Then return to the application home page and navigate to the Tools menu item. From here you can import tests from
Minerva's gradebook. In Minerva Gradebook, download the "Full Gradebook" option with all items as a CSV file. On the
web-app Import Tests page, select the module you created above and the CSV file from Minerva Gradebook. The import will
create tests for each recognised column in the gradebook.

In the Admin section of the web app you can then adjust the details of each test, such as when it is released, due, and
recommended to be done by. You can also adjust the passing mark for tests.

After creating tests, create the VITALs for the module. In the Admin pages in the VITALs section, create new VITALs by
providing a name, description, and links to the tests that determine the VITAL. Tests can be configured as sufficient,
necessary, or fractional contributors. A VITAL's name must be unique within the corresponding module.

7. Import test attempts
-----------------------

From Minerva Gradebook, download the Gradebook History report. Select all columns and CSV format. Then in the web app go
to the Tools page and select Import Minerva Attempt History. Select the module to import the test results for. The test
name from the history CSV file and the module are used to match each attempt to the correct test.

Processing test attempts can take some time, particularly if you do not restrict the report period, because there may be
thousands of attempts to process. The import process works out which students have passed which tests, then recalculates
which VITALs those students have achieved.

8. Export a module marksheet
----------------------------

The web app writes a standard Physics and Astronomy marksheet and fills in the pass/fail scores for each VITAL and the
final codes. As the modules do not have a numerical mark, the Total % column will be blank. To do this, go to the Admin
pages, click on Modules in the Minerva section, select the one module to generate a marksheet for, choose "Generate
Spreadsheet" from the action drop-down menu, and click Go. The marksheet will download.

9. Export database objects
--------------------------

To make it easier to transfer key tables such as VITALs and modules, database entities can be exported to spreadsheet
files from one instance of the application and imported into another through the backend.
