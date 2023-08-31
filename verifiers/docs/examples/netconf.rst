Netconf
=======

Implement methods
-----------------

In this section we will create custom Netconf verifier that counts the number of static routes in the device.
Example verifier is impelmented in /yang/verifiers/count_verifier.py module and
code responsible for verifying get response is shown below.

.. code-block:: python

    def get_config_verify(self, raw_response: Any) -> bool:
        # Here we have raw netconf xml response
        # We are decoding it using default netconf decoder
        # but you can use your own decode method.
        # Result will be list of tuples (value, xpath)
        try:
            decoded_response = self.decode(raw_response)
        except self.DecodeError:
            return False
        for response in decoded_response:
            for ret in self.returns:
                if response[1] == ret.xpath:
                    ret.found_items += 1
        for ret in self.returns:
            if (ret.count != ret.found_items or
                    ret.found_items < self.format['verifier']['min_count']):
                return False
        return True

Custom returns arguments
------------------------

The last step is to handle custom variables that can be passed to `returns` object.
We can do this by inheriting from `OptFields` class or creating own class and adding new fields to it and overriding
`returns` property like in example below. The `returns` object contains all values passed in returns 
section of the trigger file. In our example we will create a 3 new fields `cli_return`, `count` and `found_items`.

.. code-block:: python

    from dataclasses import field, dataclass
    from genie.libs.sdk.triggers.blitz.verifiers import NetconfDefaultVerifier
    from genie.libs.sdk.triggers.blitz.rpcverify import OptFields

    class NetconfCountVerifier(NetconfDefaultVerifier):

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
    from genie.libs.sdk.triggers.blitz.verifiers import NetconfDefaultVerifier
    from genie.libs.sdk.triggers.blitz.rpcverify import OptFields

    class NetconfCountVerifier(NetconfDefaultVerifier):

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
            return self._returns

        @returns.setter
        def returns(self, value: List[dict]) -> List[MyCustomReturns]:
            '''
            Register our custom returns class
            '''
            self._returns = [self.MyCustomReturns(**r) for r in value]

        def get_config_verify(self, raw_response: Any) -> bool:
            # Here we have raw netconf xml response
            # We are decoding it using default netconf decoder
            # but you can use your own decode method
            try:
                decoded_response = self.decode(raw_response)
            except self.DecodeError:
                return False
            for response in decoded_response:
                for ret in self.returns:
                    if response[1] == ret.xpath:
                        ret.found_items += 1
            for ret in self.returns:
                if (ret.count != ret.found_items or
                        ret.found_items < self.format['verifier']['min_count']):
                    return False
            return True


Use custom netconf verifier in test
-----------------------------------

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

    netconf_get:
        source:
            pkg: genie.libs.sdk
            class: triggers.blitz.blitz.Blitz
        test_sections:
        - validate_count:
            - yang:
                device: uut
                connection: netconf
                operation: get-config
                protocol: netconf
                datastore:
                    type: ''
                    lock: true
                    retry: 40
                content:
                    namespace:
                        oc-net: http://openconfig.net/yang/network-instance
                    nodes:
                    - nodetype: list
                    datatype: string
                    xpath: /oc-net:network-instances/oc-net:network-instance/oc-net:protocols/oc-net:protocol/oc-net:static-routes/oc-net:static
                format:
                    encoding: JSON
                    verifier:
                        class: yang.verifiers.count_verifier.NetconfCountVerifier
                        min_count: 1
                returns:
                - count: 1
                xpath: /network-instances/network-instance/protocols/protocol/static-routes/static
                cli_return: '%VARIABLES{testscript.returns}'

As you can see we definie the verifier class in the `format` section of the test case. `class` argument
is obligatory and it should point to the class that implements the verifier using dot notation.
Also you can pass any number of arguments to the verifier, like `min_count` in the example above.
Arguments passed to the verifier should be arguments that somehow are shared by all the tests that uses it.

If you wish to pass per test arguments to the verifier, you can do it in the `returns` section, like shown above.