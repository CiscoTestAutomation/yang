March 2024
==========

 - Yang v24.3 
------------------------



+-------------------------------+-------------------------------+
| Module                        | Versions                      |
+===============================+===============================+
| ``yang.connector ``           | 24.3                          |
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

* yang.ncdiff
    * Fixed order issue with leaf
        * Support RFC7950 Section 7.8.5
    * Synced below commit from ncdiff repository
        * Adjust ORDERLESS_COMMANDS https://github.com/CiscoTestAutomation/ncdiff/commit/c4fd008c23650263c0f348e77041fba0eb0ec875
        * Add another CLI that is orderless https://github.com/CiscoTestAutomation/ncdiff/commit/71741edff0ec2d08bdf63a0abcfb1f85896e38b3
        * Workaround an NVGEN issue https://github.com/CiscoTestAutomation/ncdiff/commit/45e1c4e2ad78caceed297d43578b063dadfb6ecf
        * Fixed CLI "no logging dmvpn" and "no snmp-server manager" https://github.com/CiscoTestAutomation/ncdiff/commit/f5ee87aee6a8880612f597d391bb8275406a07f2
        * New rule to remove some unnecessary commands https://github.com/CiscoTestAutomation/ncdiff/commit/ebca5cfe67f937331317b54af52510fb1f035daf
        * Add more orderless CLIs https://github.com/CiscoTestAutomation/ncdiff/commit/6d02ca73929c0548c19be486d1d18151c96c7d4a
        * Add more CLIs that do not care about the order https://github.com/CiscoTestAutomation/ncdiff/commit/7e4c82f5dbd08ee69e610ac57cc9842c1a23341e
        * CLI "crypto keyring" does not have order. https://github.com/CiscoTestAutomation/ncdiff/commit/d5f8aab68ee32841be50a3e822b3f5b71f1b56cd
        * "route-target export" and "route-target import" are orderless https://github.com/CiscoTestAutomation/ncdiff/commit/d76d7a32b60e7516f947bc834475d6917eeff6a9
        * add vlan group to orderless clis https://github.com/CiscoTestAutomation/ncdiff/commit/1307b471cf17f6e28082ab18f56266c2ac9a0b56
        * "redistribute" CLIs do not consider order https://github.com/CiscoTestAutomation/ncdiff/commit/7402e8bf07f103705e28009d2c571f73112f3a52