Gnmi
====

Implement methods
-----------------

In this section we will create custom Gnmi verifier that counts the number of static routes in the device.
First we create a new file called `count_verifier.py` in the `yang/verifiers` directory and create helper
decode method, that will be used to decode GNMI response.

.. code-block:: python

    # Import base classes. For non pyats installation you can use class provided within this module
    from genie.libs.sdk.triggers.blitz.verifiers import DefaultVerifier, BaseVerifier, GnmiDefaultVerifier
    from genie.libs.sdk.triggers.blitz.rpcverify import OptFields


    class GnmiCountVerifier(GnmiDefaultVerifier):

        def decode(self, response, namespace: dict = None, method: str = 'get') -> List[dict]:
            from genie.libs.sdk.triggers.blitz.gnmi_util import GnmiMessage
            notification = json_format.MessageToDict(response)
            updates = notification['update']['update']
            data = []
            for update in updates:
                xpath = '/'.join(
                    map(lambda up: up['name'], update['path']['elem']))
                decoded_val = GnmiMessage.decode_update_value(
                    update.get('val', {}))
                data.append({'xpath': xpath, 'value': decoded_val})
            return data


Then we will implement two methods responsible for verifing subscribe mode in GNMI `subscribe_verify` and `end_subscription`.

.. code-block:: python

    def subscribe_verify(self, raw_response: any, sub_type: str = 'ONCE', namespace: dict = None):
        decoded_response = self.decode(raw_response, 'subscribe', namespace)
        for response in decoded_response:
            for ret in self.returns:
                if ret.xpath == response['xpath']:
                    ret.found_items += len(response['value'])

    def end_subscription(self, errors):
        if errors:
            return False
        for ret in self.returns:
            if ret.count != ret.found_items or ret.found_items < self.kwargs['min_count']:
                return False
        return True

Returns custom arguments
------------------------

The last step is to handle custom variables that can be passed to `returns` object.
We can do this by inheriting from `OptFields` class or creating own class and adding new fields to it and overriding
`returns` property like in example below. The `returns` object contains all values passed in returns 
section of the trigger file. In our example we will create a 3 new fields `cli_return`, `count` and `found_items`.

.. code-block:: python

    from dataclasses import field, dataclass

    class GnmiCountVerifier(GnmiDefaultVerifier):
        @dataclass
        class MyCustomReturns:
            '''
            Create a custom returns class to be used by the verifier
            by adding new fields to the default returns dataclass.
            '''
            cli_return: dict = field(default_factory=dict)
            count: int = 0
            found_items: int = 0
            xpath: str = ''

        @property
        def returns(self) -> List[MyCustomReturns]:
            return self._returns

        @returns.setter
        def returns(self, value: List[dict]) -> List[MyCustomReturns]:
            '''
            Register our custom returns class
            '''
            self._returns = [self.MyCustomReturns(**r) for r in value]

By doing this you can now pass, your custom arguments to retruns section like this:

.. code-block:: yaml

    returns:
    - count: 2
      xpath: network-instances/network-instance/protocols/protocol/static-routes/static
      cli_return: "data"


Now let's put it all together.

.. code-block:: python

    from typing import List
    from dataclasses import field, dataclass
    from google.protobuf import json_format

    # Import base classes. For non pyats installation you can use class provided within this module
    try:
        from genie.libs.sdk.triggers.blitz.verifiers import GnmiDefaultVerifier
    except ImportError:
        from yang.verifiers.base_verifier import BaseVerifier as GnmiDefaultVerifier


    class GnmiCountVerifier(GnmiDefaultVerifier):
        from genie.libs.sdk.triggers.blitz.rpcverify import OptFields

        @dataclass
        class MyCustomReturns(OptFields):
            '''
            Create a custom returns class to be used by the verifier
            by adding new fields to the default returns dataclass
            '''
            cli_return: dict = field(default_factory=dict)
            count: int = 0
            found_items: int = 0

        @property
        def returns(self) -> List[MyCustomReturns]:
            '''
            Register our custom returns class
            '''
            return self._returns

        @returns.setter
        def returns(self, value: List[dict]) -> List[MyCustomReturns]:
            '''
            Register our custom returns class
            '''
            self._returns = [self.MyCustomReturns(**r) for r in value]

        def decode(self, response, namespace: dict = None, method: str = 'get', ) -> List[dict]:
            from genie.libs.sdk.triggers.blitz.gnmi_util import GnmiMessage
            notification = json_format.MessageToDict(response)
            updates = notification['update']['update']
            data = []
            for update in updates:
                xpath = '/'.join(
                    map(lambda up: up['name'], update['path']['elem']))
                decoded_val = GnmiMessage.decode_update_value(
                    update.get('val', {}))
                data.append({'xpath': xpath, 'value': decoded_val})
            return data

        def subscribe_verify(self, raw_response: any, sub_type: str = 'ONCE', namespace: dict = None):
            decoded_response = self.decode(raw_response, 'subscribe', namespace)
            for response in decoded_response:
                for ret in self.returns:
                    if ret.xpath == response['xpath']:
                        ret.found_items += len(response['value'])

        def end_subscription(self, errors):
            if errors:
                return False
            for ret in self.returns:
                if (ret.count != ret.found_items or
                        ret.found_items < self.format['verifier']['min_count']):
            return True


Use custom verifier in test
---------------------------

In this section we will first make a `cli` call to device to get the number of static routes and then
save it in `global variable`_.

.. _global variable: https://pubhub.devnetcloud.com/media/genie-docs/docs/blitz/design/save/index.html#re-use-variables

.. code-block:: yaml

    prepare_data:
        source:
            pkg: genie.libs.sdk
            class: triggers.blitz.blitz.Blitz
        test_sections:
        - get_routes:
            - parse: 
                device: uut
                command: show ip static route
                save:
                - variable_name: testscript.returns
                  as_dict: "%VARIABLES{action_output}"


Then we can use our custom verfier.

.. code-block:: yaml

    gnmi_subscribe_stream:
        source:
            pkg: genie.libs.sdk
            class: triggers.blitz.blitz.Blitz
        test_sections:
        - validate_count:
            - yang:
                device: uut
                connection: gnmi
                operation: subscribe
                protocol: gnmi
                content:         
                    namespace: 
                        oc-net: http://openconfig.net/yang/network-instance
                    nodes:
                    - nodetype: list
                      datatype: string
                      xpath: /oc-net:network-instances/oc-net:network-instance/oc-net:protocols/oc-net:protocol/oc-net:static-routes/oc-net:static
                format: 
                    encoding: JSON
                    request_mode: STREAM
                    sub_mode: SAMPLE
                    sample_interval: 5
                    stream_max: 10
                    verifier: 
                        class: yang.verifiers.count_verifier.GnmiCountVerifier
                        min_count: 1
                returns:
                - count: 1
                  xpath: network-instances/network-instance/protocols/protocol/static-routes/static
                  cli_return: '%VARIABLES{testscript.returns}'

As you can see we definie the verifier class in the `format` section of the test case. `class` argument
is obligatory and it should point to the class that implements the verifier using dot notation.
Also you can pass any number of arguments to the verifier, like `min_count` in the example above.
Arguments passed to the verifier should be arguments that somehow are shared by all the tests that uses it.

If you wish to pass per test arguments to the verifier, you can do it in the `returns` section, like shown above.