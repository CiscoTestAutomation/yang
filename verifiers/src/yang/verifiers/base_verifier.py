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
                 rpc_data=None,
                 **kwargs):
        super().__init__()
        self.deleted: List = []
        self.returns = returns
        self.steps = steps
        self.datastore = datastore
        self.log = log
        self.format = format
        self.kwargs = kwargs
        self.device = device
        self.rpc_data = rpc_data

    @property
    def validation_on(self) -> bool:
        return self.returns or self.deleted

    def get_config_verify(self,
                          raw_response: Any,
                          *args,
                          **kwargs) -> bool:
        """
        Used Get and Set test cases validation.

        Args:
            raw_response (any): Response received from the device.

        Returns:
            bool: Indicates if test should pass or fail.
        """
        pass

    def subscribe_verify(self,
                         raw_response: Any,
                         sub_mode: str = 'SAMPLE',
                         *args,
                         **kwargs):
        """
        Used for subscription test cases validation.
        Called on every subscription update.

        Args:
            raw_response (Any): Response received from the device.
            sub_mode (str): Gnmi subscription mode. Defaults to 'SAMPLE'.
        """
        pass

    def end_subscription(self,
                         errors: List[Exception],
                         *args,
                         **kwargs) -> bool:
        """
        Method called when subscription is ended. State should be evaluated here.

        Returns:
            bool: Indicates if test should pass or fail.
        """
        pass

    def edit_config_verify(self,
                           raw_response: Any,
                           *args,
                           **kwargs) -> bool:
        """Validation after set-config operation.

        Args:
            raw_response (any): Raw response from device.

        Returns:
            bool: Validation result.
        """
        pass

    class DecodeError(Exception):
        """General decoding error."""
        pass

    class RequestError(Exception):
        """General request error."""
        pass
