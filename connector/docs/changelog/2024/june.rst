June 2024
==========

 - Yang v24.6 
------------------------



+-------------------------------+-------------------------------+
| Module                        | Versions                      |
+===============================+===============================+
| ``yang.connector ``           | 24.6                          |
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
* yang.ncdiff
    * Updated orderless configuration:
        * Added ip ospf message-digest-key with depth 1
    * Updated orderless configuration:
        * Added mpls mldp static with depth 0
    * Updated Router orderless configuration:
        * Added router with depth 0
    * Updated orderless configuration:
        * Added device-tracking binding orderless configuration