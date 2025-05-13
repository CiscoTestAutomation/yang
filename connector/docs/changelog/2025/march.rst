March 2025
==========

March 25 - Yang v25.3 
------------------------



.. csv-table:: New Module Versions
    :header: "Modules", "Version"

    ``yang.connector``, v25.3 
    ``yang.ncdiff``, v25.3 




Changelogs
^^^^^^^^^^

yang.connector
""""""""""""""
--------------------------------------------------------------------------------
                                      New                                       
--------------------------------------------------------------------------------

* yang
    * Modified Gnmi
        * Added `skip_verify` property for `gnmi` connection
        * if `skip_verify` is set to `true` pyats will establishes a secure connection, using the server credentials.
        * Verification of certificate is skipped with this option.



yang.ncdiff
"""""""""""
