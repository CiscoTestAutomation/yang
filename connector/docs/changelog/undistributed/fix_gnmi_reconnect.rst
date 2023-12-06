--------------------------------------------------------------------------------
                                Fix
--------------------------------------------------------------------------------
* yang.connector
    * Modified class Gnmi:
        * Moved gRPC channel creation code from Gnmi __init()__ to connect() to allow re-connect.
