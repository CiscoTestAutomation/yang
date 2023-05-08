--------------------------------------------------------------------------------
                                Fix
--------------------------------------------------------------------------------
* connector
    * Removed dependency of installing pyats to use connector classes.
        * Settings class in settings.py now subclasses dict instead of AttrDict.
