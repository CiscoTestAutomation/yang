June 2026
==========

June 30 - Yang v26.6 
------------------------



.. csv-table:: New Module Versions
    :header: "Modules", "Version"

    ``yang.connector``, v26.6 
    ``yang.ncdiff``, v26.6 




Changelogs
^^^^^^^^^^
yang.connector
""""""""""""""
--------------------------------------------------------------------------------
                                      New                                       
--------------------------------------------------------------------------------

* gnmi
    * Modified Gnmi
        * Added support for commit and rollback operations


--------------------------------------------------------------------------------
                                      Fix                                       
--------------------------------------------------------------------------------

* yang.connector
    * Modified Netconf
        * Captured SSH tunnel setup and ncclient session logs in the per-connection NETCONF log file.
        * Avoided attaching the pyATS tasklog handler when its stream is unavailable.



yang.ncdiff
"""""""""""
