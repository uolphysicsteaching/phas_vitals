Quickstart
==========

This section describes how to set up and run PHAS VITALs for local development or as a private
instance. For production deployment see :ref:`label-apache2-vhost`.

1. Clone or Download the Code
-----------------------------

Download and unpack the zip file from GitHub, or clone using git::

    git clone https://github.com/uolphysicsteaching/phas_vitals.git

The repository is public and does not contain personal data or secrets. For development it is
recommended to fork the repository and work on your own fork.

2. Install Anaconda Python
--------------------------

If not already installed, download and install the latest version of `Anaconda Python
<https://www.anaconda.com/products/distribution>`_. Anaconda can be installed as an individual
user if system administrator permissions are unavailable.

3. Set Up the Conda Environment
--------------------------------

A ``environment-test.yaml`` file is provided that specifies all required Python packages::

    conda env create -f environment-test.yaml

This will take some time. Once complete, activate the environment::

    conda activate django

.. _label-quickstart-secrets:

4. Create a ``secrets.py`` Settings File
-----------------------------------------

Before the application can start, you need to provide a ``secrets.py`` file in the
``phas_vitals/settings/`` directory. This file is excluded from version control by ``.gitignore``.
For local development with an SQLite database use the following content::

    """Local secrets – keep this file out of version control!"""
    # project imports
    from .common import *  # noqa: F401, F403

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(PROJECT_ROOT_PATH / "run" / f"{SITE_NAME}.sql"),
        }
    }

5. Initialise the Database
---------------------------

Create the database tables, load initial fixtures, and collect static assets::

    python manage.py migrate
    python manage.py loaddata phas_vitals/fixtures/sitetree.json
    python manage.py collectstatic
    python manage.py createsuperuser

On Windows replace ``/`` with ``\\`` in the fixture path. The ``createsuperuser`` command will
prompt for a username, e-mail address, and password.

Several additional fixtures are provided and may be useful::

    python manage.py loaddata phas_vitals/fixtures/statuscodes.json
    python manage.py loaddata phas_vitals/fixtures/programmes.json
    python manage.py loaddata phas_vitals/fixtures/cohort.json

These load Banner ETS registration status codes, common degree programmes, and initial student
cohorts respectively.

6. Start the Development Server
--------------------------------

::

    python manage.py runserver

Then open a browser and navigate to http://127.0.0.1:8000. Log in using the superuser credentials
created above.

7. Initial Configuration
-------------------------

After logging in, open the Admin interface (``/riaradh/``) and create the following objects in
order:

1. **Cohort** objects – usually a six-digit number representing the academic year, e.g. ``202425``.
   These may have been loaded by the ``cohort.json`` fixture above.
2. **Programme** objects – one per degree programme, matching the names and codes used in Banner.
   These may have been loaded by the ``programmes.json`` fixture.
3. **Module** objects – at least one Minerva module is required. Set the module code prefix (e.g.
   ``PHAS``) in the *Constance* configuration section.
4. **Student Accounts** – these can be imported from Banner module-registration files.

8. Importing Minerva Tests
---------------------------

From the Minerva Gradebook, download the *Full Gradebook* option as a CSV file with all columns.
In the web application navigate to **Tools → Import Tests**, select the module and upload the CSV
file. The application will create a ``Test`` object for each gradebook column.

In the Admin you can then set each test's release date, due date, recommended date, and pass mark.

9. Creating VITALs
-------------------

In the Admin under **VITALs** create ``VITAL`` objects for each learning outcome in a module.
Provide a name, a description, and link the relevant tests. Tests can be marked as *sufficient*
(passing any one suffices) or *necessary* (all must be passed). A VITAL's name must be unique
within its module.

10. Importing Test Attempt History
------------------------------------

From the Minerva Gradebook, download the *Gradebook History* report as a CSV file (select all
columns). In the web application navigate to **Tools → Import Minerva Attempt History**, choose
the module, and upload the file. The application will determine which students have passed which
tests and automatically award VITALs.

11. Generating Mark-Sheets
---------------------------

In the Admin under **Minerva → Modules**, select one module and choose *Generate Spreadsheet*
from the action dropdown. Click *Go* and the mark-sheet will download as an Excel file.

12. Running Tests
------------------

The test suite uses ``pytest`` with ``pytest-django``::

    pytest

See ``TESTING.md`` in the project root for further details.
