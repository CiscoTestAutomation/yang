from typing import Any, List
from dataclasses import field, dataclass
from google.protobuf import json_format

# Import base classes. For non pyats installation you can use class provided within this module
try:
    from genie.libs.sdk.triggers.blitz.verifiers import GnmiDefaultVerifier, NetconfDefaultVerifier
except ImportError:
    from yang.verifiers.base_verifier import BaseVerifier as GnmiDefaultVerifier


class GnmiCountVerifier(GnmiDefaultVerifier):
    from genie.libs.sdk.triggers.blitz.rpcverify import OptFields

    @dataclass
    class CustomReturns(OptFields):
        '''
        Create a custom returns class to be used by the verifier
        by adding new fields to the default returns dataclass
        '''
        cli_return: dict = field(default_factory=dict)
        count: int = 0
        found_items: int = 0

    @property
    def returns(self) -> List[CustomReturns]:
        return self._returns

    @returns.setter
    def returns(self, value: List[dict]) -> List[CustomReturns]:
        '''
        Register our custom returns class
        '''
        self._returns = [self.CustomReturns(**r) for r in value]

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

    def subscribe_verify(self,
                         raw_response: any,
                         sub_type: str = 'ONCE',
                         namespace: dict = None):
        decoded_response = self.decode(
            raw_response, 'subscribe', namespace)
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
                return False
        return True


class NetconfCountVerifier(NetconfDefaultVerifier):
    from genie.libs.sdk.triggers.blitz.rpcverify import OptFields

    @dataclass
    class CustomReturns(OptFields):
        '''
        Create a custom returns class to be used by the verifier
        by adding new fields to the default returns dataclass
        '''
        cli_return: dict = field(default_factory=dict)
        count: int = 0
        found_items: int = 0

    @property
    def returns(self) -> List[CustomReturns]:
        return self._returns

    @returns.setter
    def returns(self, value: List[dict]) -> List[CustomReturns]:
        '''
        Register our custom returns class
        '''
        self._returns = [self.CustomReturns(**r) for r in value]

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
