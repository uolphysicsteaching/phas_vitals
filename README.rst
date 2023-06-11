django-project-skeleton
=======================

**django-project-skeleton** is my skeleton for Django projects. It provides a
directory structure for Django projects during development and deployment.

This fork is designed to work with Django 4.x, Python 3.11 and postgresql as the DB backend.
It adds code to automatically incorporate apps placed within the apps/ directory, looking for
a urls.py and models.py and optionally a settings.py.

Meta
----

Author:
    Mischback

Contributors:
    `agirardeaudale <https://github.com/agirardeuadale>`_,
    `jmrbcu <https://github.com/jmrbcu>`_
    `Gavin Burnell <https://github.com/gb119/>`

Status:
    maintained, in development

Version:
    1.5

Django Version:
    4.x


Usage
-----

To use this repository just use the ``template`` option of `django-admin
<https://docs.djangoproject.com/en/2.2/ref/django-admin/#startproject>`_::

    $ django-admin startproject --template=https://github.com/gb119/django-project-skeleton/archive/development.zip --name apache2_vhost.sample [projectname]

If you wish to automagically fill the ``apache2_vhost.sample`` the command is::

    $ django-admin startproject --template=https://github.com/Mischback/django-project-skeleton/archive/development.zip --name apache2_vhost.sample [projectname]


Documentation
-------------

You can see the documentation for the original version over at **Read the Docs**: `django-project-skeleton
<http://django-project-skeleton.readthedocs.org/en/latest/>`_
