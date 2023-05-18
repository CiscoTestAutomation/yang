from typing import List, Any
from abc import ABC
from logging import Logger


class BaseVerifier(ABC):
    def __init__(self,
                 device: Any,
                 returns: dict,
                 log: Logger,
                 format: dict = None,
                 steps=None,
                 datastore=None,
                 **kwargs):
        super().__init__()
        self.returns = returns
        self.steps = steps
        self.datastore = datastore
        self.log = log
        self.format = format
        self.kwargs = kwargs
        self.device = device

    def get_config_verify(self,
                          decoded_response: Any,
                          key: bool = False,
                          sequence: Any = None) -> bool:
        """
        Used by GNMI and Netconf Get and Set test cases validation.
        Called when a GetResponse is received.

        Args:
            decoded_response (any): Response received from the device and decoded
            by using the decoder method.
            key (bool, optional): Indicates if the response is a key. Defaults to False.

        Returns:
            bool: Indicates if test should pass or fail.
        """
        pass

    def gnmi_decoder(self, response: Any,
                     namespace: dict = None,
                     method: str = 'get') -> Any:
        """
        Used by GNMI to decode response before passing it to verifier.

        Args:
            response (gnmi_pb2.GetResponse | gnmi_pb2.SubscribeResponse): Response received from the device.
            namespace (dict): Namespace of module.
            method (str): Gnmi method. Defaults to 'get'.
        Returns:
            Any: Decoded response.
        """
        pass

    def netconf_decoder(self, response: Any,
                        namespace: dict = None,
                        method: str = 'get-config') -> Any:
        """
        Used by Netconf to decode response before passing it to verifier.

        Args:
            response (Any): Response received from the device.
            namespace (dict): Namespace of module.
            method (str): Netconf method. Defaults to 'get-config'.
        Returns:
            Any: Decoded response.
        """
        pass

    def restconf_decoder(self, response: Any,
                         namespace: dict = None,
                         method='') -> Any:
        """
        Used by Restconf to decode response before passing it to verifier.

        Args:
            response (gnmi_pb2.GetResponse | gnmi_pb2.SubscribeResponse): Response received from the device.
            namespace (dict): Namespace of module.
            method (str): Gnmi method. Defaults to 'get'.
        Returns:
            Any: Decoded response.
        """
        pass

    def subscribe_verify(self, decoded_response: Any, sub_mode: str = 'SAMPLE'):
        """
        Used by GNMI Subscription test cases validation.
        Called on every subscription update.

        Args:
            response (gnmi_pb2.SubscribeResponse): Response received from the device.
            sub_mode (str): Gnmi subscription mode. Defaults to 'SAMPLE'.
        """
        pass

    def end_subscription(self, errors: List[Exception]) -> bool:
        """
        Used by GNMI Subscription test cases validation.
        Method called when subscription is ended. State should be evaluated here.

        Returns:
            bool: Indicates if test should pass or fail.
        """
        pass

    def edit_config_auto_validate(self, response: any, rpc_data: dict, namespace_modules: dict) -> bool:
        """Auto-validaton after set-config operation for netconf and gnmi

        Args:
            response (any):  Decoded response received from the device.
            rpc_data (dict): Rpc data passed from test config.
            namespace_modules (dict): Namespace modules.

        Returns:
            bool: Validation result
        """
        pass

    def verify_common_cases(func) -> bool:
        """Decorator to verify common cases

        Returns:
            bool: Test result
        """
        def inner(self, response):
            # Response will be 'None' when some error is received
            if response is None:
                return False
            # Response will be empty, when no response received,
            # If returns not provided, set result false.
            elif not response and not self.returns:
                return False
            # Response is received, but user don't want to validate returns
            # set result to True as response is successfully received.
            elif response and not self.returns:
                return True
            return func(self, response)
        return inner
