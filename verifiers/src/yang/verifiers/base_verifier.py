from typing import List, Any
from abc import ABC
from logging import Logger


class BaseVerifier(ABC):
    def __init__(self, device: Any, returns: dict, log: Logger, **kwargs):
        super().__init__()
        self.returns = returns
        self.log = log
        self.kwargs = kwargs
        self.device = device

    def get_config_verify(self,
                          decoded_response: Any,
                          key: bool = False,
                          sequence: Any = None) -> bool:
        """
        Used by GNMI Get and Set test cases validation.
        Called when a GetResponse is received.

        Args:
            response (gnmi_pb2.GetResponse): Response received from the device.

        Returns:
            bool: Indicates if test should pass or fail.
        """
        return True

    def get_config_decoder(self, response: Any, namespace: dict = None) -> Any:
        return ''

    def subscribe_verify(self, decoded_response: Any, sub_mode: str = 'SAMPLE'):
        """
        Used by GNMI Subscription test cases validation.
        Called on every subscription update.

        Args:
            response (gnmi_pb2.SubscribeResponse): Response received from the device.
        """
        return True

    def subscribe_decoder(self, response: Any, namespace: dict = None) -> Any:
        return ''

    def end_subscription(self, errors: List[Exception]) -> bool:
        """
        Used by GNMI Subscription test cases validation.
        Method called when subscription is ended. You should evaluate your
        state here.

        Returns:
            bool: Indicates if test should pass or fail.
        """
        return True
