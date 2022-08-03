--------------------------------------------------------------------------------
                                Fix
--------------------------------------------------------------------------------
* yang.connector
    * Modified Gnmi and GnmiNotification classes:
        * No functionality change. Did small refactors/fixes
            * fixed passing mutable object as default to function
            * fixed typo
            * removed try/except where hiding exceptions
            * changed to f-strings where possible