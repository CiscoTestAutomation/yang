January 2024
==========

30 - Yang v24.1 
------------------------



+-------------------------------+-------------------------------+
| Module                        | Versions                      |
+===============================+===============================+
| ``yang.connector ``           | 24.1                          |
+-------------------------------+-------------------------------+

Upgrade Instructions
^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

    pip install --upgrade yang.connector




Changelogs
^^^^^^^^^^
--------------------------------------------------------------------------------
                                      Fix                                       
--------------------------------------------------------------------------------

* yang.connector
    * Modified class Gnmi
        * Moved gRPC channel creation code from Gnmi __init()__ to connect() to allow re-connect.
    * Fix ut for re_connect
    * Pinning lxml in setup.py to fix xml error
    * Modified imports
        * Added conditional imports to allow library to be used without pyats install.


