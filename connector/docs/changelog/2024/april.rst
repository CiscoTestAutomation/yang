April 2024
==========

 - Yang v24.4 
------------------------



+-------------------------------+-------------------------------+
| Module                        | Versions                      |
+===============================+===============================+
| ``yang.connector ``           | 24.4                          |
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
        * added redistribute under eigrp topology
        * added distribute-list under ipv6 router eigrp