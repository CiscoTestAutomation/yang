November 2023
=============

+-------------------------------+-------------------------------+
| Module                        | Versions                      |
+===============================+===============================+
| ``yang.ncdiff``               | 23.11                         |
+-------------------------------+-------------------------------+


Fixes:
^^^^^^^^^

* ncdiff
    * updated scan_models()
        * avoid scanning models again if models were already scanned
    * updated load_model()
        * avoid loading models again if models were already loaded