from logging import Logger
from typing import Any, List
from genie.libs.sdk.triggers.blitz.rpcverify import BaseVerifier, DefaultVerifier, OptFields
from genie.libs.sdk.triggers.blitz.gnmi_util import GnmiMessage
from dataclasses import field, dataclass
from google.protobuf import json_format


class CountVerifier(DefaultVerifier):

    @dataclass
    class MyCustomReturns(OptFields):
        '''
        Create a custom returns class to be used by the verifier
        by adding new fields to the default returns dataclass
        '''
        cli_return: dict = field(default_factory=dict)
        count: int = 0

    @property
    def returns(self) -> List[MyCustomReturns]:
        return self._returns

    @returns.setter
    def returns(self, value: List[dict]) -> List[MyCustomReturns]:
        '''
        Register our custom returns class
        '''
        self._returns = [self.MyCustomReturns(**r) for r in value]

    def __init__(self, device: Any, returns: dict, log: Logger, **kwargs):
        super().__init__(device, returns, log, **kwargs)

    def subscribe_decoder(self, response, namespace: dict = None) -> List[dict]:
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

    def subscribe_verify(self, decoded_response: dict, sub_type: str = 'ONCE'):
        for response in decoded_response:
            for ret in self.returns:
                if ret.xpath == response['xpath']:
                    ret.count += len(response['value'])

    def end_subscription(self, errors):
        if errors:
            return False
        for ret in self.returns:
            if ret.count != ret.value:
                return False
        return True
