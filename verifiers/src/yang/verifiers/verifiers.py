from typing import List
from dataclasses import field, dataclass
from google.protobuf import json_format

# Import base classes. For non pyats installation you can use class provided within this module
try:
    from genie.libs.sdk.triggers.blitz.verifiers import DefaultVerifier
except ImportError:
    from yang.verifiers.base_verifier import BaseVerifier as DefaultVerifier


class CountVerifier(DefaultVerifier):
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
        return self._returns

    @returns.setter
    def returns(self, value: List[dict]) -> List[MyCustomReturns]:
        '''
        Register our custom returns class
        '''
        self._returns = [self.MyCustomReturns(**r) for r in value]

    def gnmi_decoder(self, response, namespace: dict = None, method: str = 'subscribe') -> List[dict]:
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

    def subscribe_verify(self, decoded_response: dict, sub_type: str = 'ONCE'):
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
