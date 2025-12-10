December 2025
==========

December 30 - Yang v25.11
------------------------



.. csv-table:: New Module Versions
    :header: "Modules", "Version"

    ``yang.connector``, v25.11
    ``yang.ncdiff``, v25.11




Changelogs
^^^^^^^^^^

yang.connector
""""""""""""""

yang.ncdiff
"""""""""""
--------------------------------------------------------------------------------
                                      Fix                                       
--------------------------------------------------------------------------------

* yang.ncdiff
    * NETCONF masking to hide encrypted values  in get-config while preserving unmasked data for edit-config.
    * Added _normalize_passwords() helper function normalization replaces the hash portion of any password 6 line.


