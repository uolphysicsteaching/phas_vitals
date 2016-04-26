django-project-skeleton
=======================

**django-project-skeleton** is my skeleton for Django projects. It provides a
directory structure for Django projects during development and deployment.


Meta
----

Author:
    Mischback
    Gavin Burnell (this fork)

Status:
    maintained, in development

Version:
    1.2

Django Version:
    1.9



Usage
-----

To use this repository just use the ``template`` option of `django-admin and run

    $ django-admin startproject --template=https://github.com/gb119/django-project-skeleton/archive/development.zip --name apache2_vhost.sample [projectname]

to automagically fill the ``apache2_vhost.sample``.


Documentation
-------------

You can see the documentation for the original version over at **Read the Docs**: `django-project-skeleton
<http://django-project-skeleton.readthedocs.org/en/latest/>`_

This fork updates some things for Django 1.9 and Apache 2.4 and changes a few defaults to thinks I like better.