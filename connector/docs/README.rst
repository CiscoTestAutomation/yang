.. _yang.connector:


Introduction
============

This module defines a set of classes that connect to Data Model Interfaces
(DMI), in particular, an implementation of Netconf client. Restconf
implementation is coming soon.

Quick examples can be found in :doc:`apidocs`.

Features
--------

* NETCONF v1.0 and v1.1 compliant (RFC 6241)
* NETCONF over SSH (RFC 6242) including Chunked Framing Mechanism
* pyATS compliant

  This module is fully integrated into pyATS. Starting from pyATS 3.1.0, the introduction
  of pyATS Connection Manager allows us to establish Netconf connections
  seamlessly in pyATS topology model. More details of Connection Manager can be
  found in
  `Connection Meta <http://wwwin-pyats.cisco.com/documentation/latest/connections/index.html>`_
  .

Upcoming features include configuration data model message builder objects for
Netconf and Restconf, and operational data model parser objects for Netconf and
Restconf with integration of new
`Genie <http://wwwin-pyats.cisco.com/cisco-shared/genie/latest/>`_
and
`Metaparser <http://wwwin-pyats.cisco.com/cisco-shared/metaparser/latest/>`_
model.

Comparison to Other Netconf Clients
-----------------------------------

There are a few more Netconf client software available:

* `ConfD Netconf Server <http://www.tail-f.com/confd-netconf-server/>`_ includes
  a Netconf python-based client. ConfD Netconf Server is rich in features, but
  for Netconf testing purpose, it might be too heavy.
* `ncclient <https://pypi.python.org/pypi/ncclient>`_ package in PyPi is a
  Python library for Netconf client side scripting.
* `MG-SOFT Netconf/Yang Python Scripting System
  <http://www.mg-soft.com/mgProductsNetConf.html?p1=products>`_ is a
  **commercial** Netconf client scripting framework, which consists of three
  components: Netconf Script API, YANG Python layer, and a GUI tool that lets
  you generate Python classes from YANG modules.
* `libnetconf <https://github.com/CESNET/libnetconf>`_ is a Netconf library in
  C language and it can be used to build Netconf servers and clients.
  libnetconf has Python bindings called pynetconf that requires distutils
  Python module. libnetconf is being used by some teams in Cisco.

These Netconf client softwares are all viable options to serve different
purposes. However, Yang module is designed to integrate into pyATS environment
and to meet Cisco internal data model testing requirements.

Data Model Testing in Cisco
---------------------------

Cisco is committed to deliver device operational consistency and alignment,
full automation of device lifecycle operations, and simplicity in device
management through data model driven programmatic interfaces. As a result,
data model testing is beginning to take hold at Cisco and its importance is
increasing. Traditional CLI-based testing is evolving when customers start to
demand more data model driven interfaces.

Yang module is an attempt responding to future data model testing needs.


Governance
==========
- Users are encouraged to contribute to Yang module as data model testing
  becomes more popular.
- Any questions or requests may be sent to yang-python@cisco.com.


Installation
============

yang.connector module requires pyATS, which will be briefly described first.
Then yang.connector package installation section is followed.

pyATS Installation
------------------

User needs to create an empty directory and inside that new directory
the installation script can be called.

.. code-block:: text

    cd <your pyATS root instance directory>
    /auto/pyats/bin/pyats-install

.. note::

    ``--help`` can be used to check installation options

In order to activate your pyATS instances, i.e., your Python
virtual environments, users may cd to your pyATS root directory and source the
environment shell script, `env.sh` or `env.csh`, depending on your shell type.

.. code-block:: text

    cd <your pyATS root instance directory>
    source env.sh

For more information about pyATS
`installation <http://wwwin-pyats.cisco.com/documentation/html/install/install.html>`_
please check the documentation.

yang.connector Package Installation
-----------------------------------

After pyATS installation, this package can be installed from pypi server
(using `pip`).

First-time installation steps (use `env.sh` as an example):

.. code-block:: text

    cd <your pyATS root instance directory>
    pip install yang.connector


Steps to upgrade to latest (use `env.sh` as an example):

.. code-block:: text

    cd <your pyATS root instance directory>
    pip install --upgrade yang.connector


.. sectionauthor:: Jonathan Yang <yuekyang@cisco.com>
