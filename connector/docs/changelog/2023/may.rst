May 2023
==========

May 30 - Yang v23.5 
------------------------



+-------------------------------+-------------------------------+
| Module                        | Versions                      |
+===============================+===============================+
| ``yang.connector ``           | 23.5                          |
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

* connector
    * Removed dependency of installing pyats to use connector classes.
        * Settings class in settings.py now subclasses dict instead of AttrDict.


