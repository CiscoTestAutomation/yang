Verifiers Installation
======================

In order to implement your custom verifier you need to fork repository and install it. Then
you can add your custom verifiers into installed package.

First of all, you need to fork `yang.verifiers repository`_ and clone it to your local machine. Then follow steps
below to install it.

.. _yang.verifiers repository: https://github.com/CiscoTestAutomation/yang

.. code-block:: console

    $ ls
    LICENSE  NOTICE  README.md  connector  ncdiff  verifiers
    $ cd verifiers
    $ make develop
