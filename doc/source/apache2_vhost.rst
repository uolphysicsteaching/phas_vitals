.. _label-apache2-vhost:

Apache2 Virtual Host Configuration
====================================

A sample Apache2 configuration for deploying PHAS VITALs with ``mod_wsgi`` is
provided at ``configs/apache2_vhost.sample``.

Usage
-----

The file contains two types of placeholders:

``[[placeholder_name]]``
    Must be replaced manually. Most notably:

    * ``[[SERVER_NAME]]`` – the fully qualified domain name of the server (e.g.
      ``phas-vitals.leeds.ac.uk``).
    * ``[[your email]]`` – the server administrator's e-mail address.

``W:\\phas_vitals\\phas_vitals/…``
    File system paths. Replace with the actual absolute path to the project root
    on your server (Linux paths use forward slashes, Windows paths use backslashes).

Concept
-------

The configuration sets up a name-based virtual host on port 80 that serves the
application via ``mod_wsgi`` in daemon mode. Static and media files are served
directly by Apache to avoid routing them through Django.

Key directives
^^^^^^^^^^^^^^

``Alias /static/   <project_root>/run/static/``
    Serve static files from ``STATIC_ROOT`` under ``STATIC_URL``. Remember to
    run ``python manage.py collectstatic`` before starting Apache.

``Alias /media/   <project_root>/run/media/``
    Serve user-uploaded media from ``MEDIA_ROOT`` under ``MEDIA_URL``.

``WSGIScriptAlias /   <project_root>/phas_vitals/wsgi.py``
    Route all other requests through the Django WSGI application.

``WSGIDaemonProcess phas_vitals python-path=<project_root>``
    Run the WSGI process as a daemon named ``phas_vitals``. Add the project root
    to the Python path so that Django can find the ``phas_vitals`` package.

``WSGIProcessGroup phas_vitals``
    Associate the virtual host with the daemon process group.

Production Considerations
--------------------------

* For production use SSL/TLS (HTTPS). The ``production.py`` settings module
  enables ``SECURE_SSL_REDIRECT``, so HTTP requests will be redirected to HTTPS.
  Configure a port 443 virtual host with a valid certificate.
* Set ``DEBUG = False`` in your ``secrets.py``.
* Ensure the ``run/`` directory (including ``logs/``, ``media/``, and ``static/``)
  is writable by the Apache process user.
* The ``run/SECRET.key`` file should be readable only by the Apache process user.
* Consider using ``mod_wsgi``'s ``WSGIApplicationGroup %{GLOBAL}`` directive if
  you run multiple Django applications on the same server.

Source
------

.. literalinclude:: ../../configs/apache2_vhost.sample
    :language: apache
    :linenos:
