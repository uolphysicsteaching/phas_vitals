Physics VITALs Reporting Tool
=============================

Overview
~~~~~~~~

This web application is designed to support the 2024/25 onwards Physics and Astronomy Programmes at the University
of Leeds. Its overall task is to collect test scores from the Balackboard Ultra instance, compare scores to per-score
pass marks and then to use the pass/fail status of individual tests to map to pass/fail status of a student's
*Verifiable Indicators of Thresold Ability and Learning* - VITALs. Finally the application should be able to produce
a suitable mark-sheet for recording the student progress.

Local (Development) Setup
~~~~~~~~~~~~~~~~~~~~~~~~~~

Althouugh the web-app i designed for deployment as a WSGI application on a web-server with networked database server -
such as Gunicorn/Nginx/PostGresql - it is straightforward to setup and run as a local application, either for
development or as a 'private' instance.

This section will provide an overview of the steps to set this app up in local mode.

1. Clone or Download the Code
-----------------------------

Download and unpack the zip file of this code from github https://github.com/uolphysicsteaching/phas_vitals

The repository is public (and doesn't contain any personal data or secrets!). For development, it is recommended to
fork the repository and use git.

2. Install Anaconda Python
--------------------------

If not already installed, download and install the latest version of Anaconda Python (this can be installed as an
individual user if system administrator permissions are not available.)

3. Setup the conda environment
------------------------------

The web app comes with a file that describes all the python packages that are required to be installed to run it.
The *environment.yaml* file will specify packages from the main anaconda repository, the conda-forge repository, and
several from my own published repository of packages. Open a Anaconda Powershell prompt/shell window and change
diretory to the location where the code has been unpacked::

    conda env create -f environment.yaml

This will take some time to execute so please be patient. After it has finished, activate the new conda environment::

    conda activate django

4. Setup the Database etc.
--------------------------

Before you can use the application, you need to give it a database to use. This should be configured as a file:
*secrets.py* that is placed in the phas_vitals/settings/ directory. For local operations, an SQLLITE database can be
easily setup using the following file::

    """
    Ensure that this file is in .gitignore !"""
    # app imports
    from .common import *

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(PROJECT_ROOT_PATH / "run" / f"{SITE_NAME}.sql"),
        }
    }

This will store the database locally within the run/ directory (the project is setup so that neither the secrets.py
file, nor the database will be saved to github by accident).

Once this is done, you need to create the databases, load in some initial values and ensure that all the necessary
resources are collected::

    python manage.py migrate
    python manage.py loaddata phas_vitals/fixtures/sitetree.json
    python manage.py collectstatic
    python manage.py createsuperuser

In the second command the forward-slash / will need to be a back-slash \ in Windows. The third command will prompt to
confirm a copy and the fourth command will prompt for a username (typically Admin), email address and password.

There are some additional fixtures that will probably be useful::

    python manage,py loaddata phas_vitals/fixtures/statuscodes.json
    python manage,py loaddata phas_vitals/fixtures/programmes.json
    python manage,py loaddata phas_vitals/fixtures/cohort.json
    
These load the Banner ETS registration codes into the site, the common programmes for students, and some initial student cohorts.

5. Startup the Local Server and Connect to the App
--------------------------------------------------

Now start the web-app with::

    python manage.py runserver

Finally open a web-browser and connect to http://127.0.0.1:8000

You will be able to login with the credentials set above for the superuser account.

6. Configure The App.
---------------------

After logging in, click on the Admin menu item to access the backend of the system. Using this you can create
database entries for everything the system requires. Start by creating the following:

    - Cohort objects: Usually specifed as a 6 digit number to represent the academic year, e.g. 202425 - may be loaded by the cohort.json fixture above
    - Programme Objects: You will need to create a Programme object for each degree programme that a student might
      be studying. These should match the name and code used by Banner/ Maybe loaded from the programmes.json fixture above.
    - Student Accounts - these can be imported from Banner module registration files (** needs sorting **) and will
      create user accounts for each student enrolled on the system.
    - Module objects - these are in the minerva section. At least one Module object will be required and the details.
      provided. Key details and the name and module code. The module code prefix (e.g. PHAS) also needs to be set in
      the *constance* section.

Then go back to the application home page and navigate to the Tools menu item. From here you can import the Tests from
Minerva's gradebook. In Minerva Gradebook, download the "Full Gradebook" option with all items and as a csv file. Then
on the web-app Import Tests page you can select the module you created above, and the .csv file from Minerva Gradebook
and it will create tests for each column in the Gradebook.

In the Admin section of the web-app you can then adjust the details of the test, such as when they are released, due,
and recommened to be done by. You can also adjust the passing mark for the tests.

After creating the Tests, you need to create the VITALs for the module. In the Admin pages int he Vitals section
you can create new VITALs, providing a name, description and linking them to passing Tests. Tests can be set as
sufficient to pass a VITAL and also necessary to pass a VITAL. A VITAL is passed if any sufficient test is passed, or
all necessary tests are passed. A VITAL's name must be unique to the corresponding module.'

7. Importing Test Attempts
--------------------------

From Minerva Gradebook, download the Gradebook History report. Select all columns, and csv format. Then in the Web-App
go to the Tools page and seelect Import Minerva Attempt History. Select the module to import the test results for.
The Test name from the history csv file and module are used to match the attempt to the correct test.

Processing the test attempts can take some time - particularly if you do not restrict the time period to report for as
there may well be thousands of atempts to deal with. The import process will work out which students have passed which
tests, and therefore which VITALs automatically.

8. Export a Module Mark Sheet
-----------------------------

The Web-App will write a standard Physics and Astronomy mark sheet and fill in the P/F scores for each VITAL and also
the final codes. As the modules do not have a numerical mark, the Total % column will be blank. To do this, go to
the Admin pages, click on Modules in the minerva section.From the list of modules, select the ONE module to generate
a marksheet for and then select "Generate Spreadsheet" from the drop down menu of actions. Finally click Go and the
marksheet will download.

9. Exporting Database Objects
-----------------------------

To make it easier to transfer key tables like VITALS and Modules, all the database entieis can be exported to spreadhseet
files from one instance of the application and imported into another bia the backed.
