.. _label-project-settings:

Settings
========

The settings module lives in ``phas_vitals/settings/`` and is split across several files to
separate concerns. The active settings file is determined at runtime by the
``DJANGO_SETTINGS_MODULE`` environment variable. ``manage.py`` defaults to
``phas_vitals.settings.development``.


common.py
---------

Shared settings used by all environments. All other settings files import from this module
(directly or transitively via ``secrets.py``).

Path Configuration
^^^^^^^^^^^^^^^^^^

``DJANGO_ROOT_PATH``
    Absolute ``Path`` to the Django project package directory (``phas_vitals/``).

``PROJECT_ROOT_PATH``
    Absolute ``Path`` to the project root directory.

``SITE_NAME``
    Derived from the Django root directory name (``phas_vitals``).

``STATIC_ROOT``
    Directory where ``collectstatic`` places processed static assets:
    ``<project_root>/run/static``.

``MEDIA_ROOT``
    Directory for user-uploaded files: ``<project_root>/run/media``.

``STATICFILES_DIRS``
    Additional locations Django searches for static assets:
    ``[<project_root>/static]``.

``PROJECT_TEMPLATES``
    Directories Django searches for project-wide templates:
    ``[<project_root>/templates]``.

``STORAGES``
    Configures ``whitenoise.storage.CompressedManifestStaticFilesStorage`` for
    static files and the default ``FileSystemStorage`` for uploaded media.

Application Configuration
^^^^^^^^^^^^^^^^^^^^^^^^^

``APPS``
    A dictionary of custom application directories discovered automatically from
    ``<project_root>/apps/``. Any sub-directory that contains a ``models.py`` file
    is included.

``CUSTOM_APPS``
    List of app module names derived from ``APPS``, added to ``INSTALLED_APPS``
    automatically.

``DEFAULT_APPS``
    Full ``INSTALLED_APPS`` list combining Django built-ins, third-party packages,
    ``CUSTOM_APPS``, and ``baton.autodiscover``. Key third-party apps include:

    * ``baton`` – Baton admin theme
    * ``adminsortable2`` – drag-and-drop ordering in the admin
    * ``django_htmx`` – HTMX middleware and utilities
    * ``ajax_select`` – AJAX autocomplete widgets
    * ``constance`` – database-backed dynamic settings
    * ``dal`` / ``dal_select2`` – django-autocomplete-light
    * ``django_bootstrap5`` – Bootstrap 5 form rendering
    * ``django_filters`` – queryset filtering
    * ``django_tables2`` – table rendering
    * ``django_auth_adfs`` – ADFS / Azure AD single sign-on
    * ``import_export`` – admin import/export via django-import-export
    * ``oauth2_provider`` – OAuth2 provider
    * ``rest_framework`` – Django REST Framework
    * ``sitetree`` – navigation tree management
    * ``tinymce`` – TinyMCE rich-text editor
    * ``django_celery_results`` / ``django_celery_beat`` – Celery task backend

``MIDDLEWARE``
    Standard Django middleware plus:

    * ``django_htmx.middleware.HtmxMiddleware``
    * ``whitenoise.middleware.WhiteNoiseMiddleware``
    * ``django.contrib.flatpages.middleware.FlatpageFallbackMiddleware``

``TEMPLATES``
    Single Django template backend with ``APP_DIRS = True``. Context processors
    include those for auth, constance, request, i18n, media, static, and messages.
    Built-in template tags include ``django.templatetags.static``,
    ``mathfilters``, and ``phas_vitals.templatetags.phas_tags``.

Authentication Configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``AUTH_USER_MODEL``
    Set to ``accounts.Account`` – the project's custom user model.

``LOGIN_URL``
    ``django_auth_adfs:login`` – users are sent to the ADFS login page by default.

``LOGIN_REDIRECT_URL``
    ``"/"`` – redirect to home after successful login.

``LOGOUT_REDIRECT_URL``
    ``"/"`` – redirect to home after logout.

``AUTHENTICATION_BACKENDS``
    Ordered list:

    1. ``util.backend.LeedsAdfsBaseBackend`` – University of Leeds ADFS backend
    2. ``django.contrib.auth.backends.ModelBackend`` – standard Django backend

``AUTH_ADFS``
    ADFS / Azure AD configuration including claim mapping for ``first_name``,
    ``last_name``, and ``email``.

Security Configuration
^^^^^^^^^^^^^^^^^^^^^^

``SECRET_FILE``
    Path to a file holding the Django ``SECRET_KEY``:
    ``<project_root>/run/SECRET.key``. The key is auto-generated on first run if
    the file does not exist.

``ADMINS`` / ``MANAGERS``
    Set to the project maintainer. These accounts receive error notification
    e-mails.

``ALLOWED_HOSTS``
    Automatically populated from the server's DNS name and IP address, plus
    ``localhost`` and ``127.0.0.1``. Additional test-server entries are included.

``CSRF_TRUSTED_ORIGINS``
    HTTPS origins derived from ``ALLOWED_HOSTS``.

``SESSION_EXPIRE_AT_BROWSER_CLOSE``
    ``True`` – sessions end when the browser is closed.

``SESSION_COOKIE_AGE``
    ``7200`` seconds (2 hours) before a session expires.

Django Running Configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``WSGI_APPLICATION``
    ``phas_vitals.wsgi.application``

``ROOT_URLCONF``
    ``phas_vitals.urls``

``SITE_ID``
    ``1``

``STATIC_URL``
    ``/static/``

``MEDIA_URL``
    ``/media/``

``DEFAULT_AUTO_FIELD``
    ``django.db.models.AutoField``

``DEBUG``
    ``False`` in ``common.py``; overridden per environment (see below).

Internationalisation
^^^^^^^^^^^^^^^^^^^^

``LANGUAGE_CODE``
    ``"en"``

``TIME_ZONE``
    ``"Europe/London"``

``USE_I18N``
    ``True``

``USE_TZ``
    ``True``

Logging
^^^^^^^

Log files are written to ``<project_root>/logs/``:

* ``django.log`` – general debug log (verbose format)
* ``htmx.log`` – HTMX view debug log
* ``form_data.log`` – form-processing info log
* ``debug.log`` – additional debug output

Error-level messages are also e-mailed to ``ADMINS`` via ``AdminEmailHandler``
(with a filter to suppress routine noise).

E-mail Configuration
^^^^^^^^^^^^^^^^^^^^

``EMAIL_BACKEND``
    ``django.core.mail.backends.smtp.EmailBackend``

``EMAIL_HOST``
    ``smtp.leeds.ac.uk``

``EMAIL_PORT``
    ``25``

``DEFAULT_FROM_EMAIL``
    ``no-reply@phas_vitals.leeds.ac.uk``

Constance (Dynamic Settings)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``CONSTANCE_BACKEND``
    ``constance.backends.database.DatabaseBackend`` – settings are stored in the
    database and editable through the admin.

``CONSTANCE_CONFIG``
    ``SUBJECT_PREFIX`` – the module subject code prefix used when searching for
    modules (default ``"PHAS"``).

Third-party App Settings
^^^^^^^^^^^^^^^^^^^^^^^^^

``BATON``
    Configures the Baton admin theme: site header, title, dark mode, gravatar
    support, and the custom admin navigation menu.

``DJANGO_TABLES2_TEMPLATE``
    ``"django_tables2/bootstrap5-responsive.html"``

``REST_FRAMEWORK``
    Requires admin permission by default. Supports session and basic authentication.
    Uses ``DjangoFilterBackend`` and rate-throttling (100/hour anonymous,
    1000/hour authenticated).

``CELERY_RESULT_BACKEND``
    ``"django-db"`` – task results are stored in the database via
    ``django-celery-results``.

``SITETREE_CLS`` / ``SITETREE_MODEL_TREE`` / ``SITETREE_MODEL_TREE_ITEM``
    Customise the sitetree navigation library to use the project's
    ``GroupedTree`` and ``GroupedTreeItem`` models from the ``util`` app.

Per-app Settings
^^^^^^^^^^^^^^^^

Each app in ``CUSTOM_APPS`` may provide a ``settings.py`` module. Settings are
automatically imported from each such module:

* Dictionary settings are merged into the global setting.
* List/tuple settings are appended.
* Other settings replace the global value.


development.py
--------------

Used for local development. Imports ``secrets.py`` (not in version control) which
provides ``DATABASES`` and any other local overrides::

    from .secrets import *  # noqa

Additionally sets:

``DEBUG``
    ``False`` (override to ``True`` in your ``secrets.py`` when needed).

``ALLOWED_HOSTS``
    ``["*"]`` – accept connections from any host.

``INSTALLED_APPS``
    Set to ``DEFAULT_APPS`` (includes all auto-discovered custom apps).


production.py
-------------

Imports all settings from ``development.py`` and then adds security hardening:

``SECURE_HSTS_SECONDS``
    ``3600``

``SECURE_SSL_REDIRECT``
    ``True`` – redirect all HTTP requests to HTTPS.

``SESSION_COOKIE_SECURE`` / ``CSRF_COOKIE_SECURE`` / ``CSRF_COOKIE_HTTPONLY``
    All ``True``.

``X_FRAME_OPTIONS``
    ``"DENY"``

``SECURE_HSTS_INCLUDE_SUBDOMAINS``
    ``True``


i18n.py
-------

Optional file containing internationalisation and localisation settings.
Import it explicitly in ``development.py`` or ``production.py`` if required.

``LANGUAGE_CODE``, ``TIME_ZONE``, ``USE_I18N``, ``USE_L10N``, ``USE_TZ``
    Standard Django i18n settings.

``LANGUAGES``
    A list of languages supported by the project.

``LOCALE_PATHS``
    Filesystem locations for translation catalogues.


test.py
-------

Settings for the test suite (used by ``pytest-django``). Overrides:

* Database to use an in-memory SQLite instance.
* Disables password hashing to speed up tests.
* Sets ``CELERY_TASK_ALWAYS_EAGER = True`` so tasks run synchronously.


secrets.py
----------

**Not included in version control.** Must be created manually in
``phas_vitals/settings/``. At a minimum it should import from ``common.py`` and
define ``DATABASES``. See :ref:`quickstart <label-quickstart-secrets>` for an
example SQLite configuration.
