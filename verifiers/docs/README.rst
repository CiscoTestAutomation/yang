
Docs: `https://yangconnector.readthedocs.io/en/latest/ <https://yangconnector.readthedocs.io/en/latest/>`_

GitHub: `https://github.com/CiscoTestAutomation/yang.git <https://github.com/CiscoTestAutomation/yang.git>`_

Introduction
============
This module allows users to create their own verifiers for pyATS genie by implementing
base classes defined in this module.

Before implementing a custom verifier make sure you :doc:`installed yang.verifiers. </installation>`

Now in order to implement a custom verifier you need to create a new file in the `yang/verifiers` directory.
Then you need to create a new class that inherits from one BaseVerifier or DefaltVerifier classes.
Then you can implement methods that you need. List of avaliable methods can be found :doc:`here. </apidocs>`

Click here to see example :doc:`example</examples/index>` verifiers.
