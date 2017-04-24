April 2017
==========

April 24
--------

.. csv-table:: Module Versions
    :header: "Modules", "Versions"

        ``yang.connector``, v2.0.1

Features:
^^^^^^^^^

  - Support of overriding attributes that provided in YAML file. For example,
    device.connect(alias='nc', via='netconf', username='lab', password='lab')
    allows you to use username lab and password lab instead of what are in the
    YAML file.
