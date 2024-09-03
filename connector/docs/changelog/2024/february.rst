February 2024
==========

February 27 - Yang v24.2 
------------------------



+-------------------------------+-------------------------------+
| Module                        | Versions                      |
+===============================+===============================+
| ``yang.connector ``           | 24.2                          |
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
    * updated `request` method
* yang.ncdiff
    * synced PR2, 3, 5, 8, 13, 14, 19, 21, 24, 25, 26 and 27 from ncdiff repository
    * updated NetconfCalculator class
        * added diff_type `minimum-replace`
        * added `add_attribute_at_depath` method
        * added `add_attribute_by_xpath` method
        * added `find_by_tags` method
    * updated ConfigDelta class
        * added `replace_xpath` argument