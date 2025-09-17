--------------------------------------------------------------------------------
                                Fix
--------------------------------------------------------------------------------
* yang.ncdiff
    * Removed `username` from ORDERLESS_COMMANDS to fix false diffs where unchanged global lines appeared as removed/added.