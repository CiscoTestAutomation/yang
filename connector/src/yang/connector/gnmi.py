import os
import copy
import logging
from collections.abc import Iterable
from collections import OrderedDict
import base64
import json
from threading import Thread, Event
from time import sleep
from datetime import datetime
from six import string_types
from xml.etree.ElementPath import xpath_tokenizer_re

from google.protobuf import json_format

from cisco_gnmi import ClientBuilder
from cisco_gnmi import client

from . import xpath_util

try:
    from pyats.log.utils import banner
    from pyats.connections import BaseConnection
    from pyats.utils.secret_strings import to_plaintext
except ImportError:
    # Standalone without pyats install
    class BaseConnection:
        class dev:
            def __init__(self, dev_os):
                self.os = dev_os

        def __init__(self, device_os, **kwargs):
            self.connection_info = {'protocol': 'gnmi'}
            self._device = self.dev(device_os)
            self.connection_info.update(kwargs)

    def banner(string):
        return string

    def to_plaintext(string):
        return string

# create a logger for this module
log = logging.getLogger(__name__)
# Set debug level for cisco_gnmi.client
client.logger.setLevel(logging.DEBUG)


class gNMIException(IOError):
    pass


class GnmiNotification(Thread):
    """Thread listening for event notifications from the device."""

    def __init__(self, device, response, **request):
        Thread.__init__(self)
        self.device = device
        self._stop_event = Event()
        self.log = logging.getLogger(__name__)
        self.log.setLevel(logging.DEBUG)
        self.request = request
        self.responses = response

    @property
    def request(self):
        return self._request

    @request.setter
    def request(self, request={}):
        self.returns = request.get('returns')
        self.response_verify = request.get('verifier')
        self.decode_response = request.get('decode')
        self.namespace = request.get('namespace')
        self.sub_mode = request['format'].get('sub_mode', 'SAMPLE')
        self.encoding = request['format'].get('encoding', 'PROTO')
        self.sample_interval = request['format'].get('sample_interval', 10)
        self.stream_max = request['format'].get('stream_max', 0)
        self.time_delta = 0
        self.result = None
        self.event_triggered = False
        self._request = request

    def process_opfields(self, response):
        """Decode response and verify result.

        Decoder callback returns desired format of response.
        Verify callback returns verification of expected results.

        Args:
          response (proto.gnmi_pb2.Notification): Contains updates that
              have changes since last timestamp.
        """
        subscribe_resp = json_format.MessageToDict(response)
        updates = subscribe_resp['update']
        for update in updates['update']:
            resp = self.decode_response(update, self.namespace)
            if self.event_triggered:
                if resp:
                    if not self.returns:
                        self.log.error('No notification values to check')
                        self.result = False
                        self.stop()
                    else:
                        self.result = self.response_verify(resp, self.returns.copy())
                else:
                    self.log.error('No values in subscribe response')

    def run(self):
        """Check for inbound notifications."""
        t1 = datetime.now()
        self.log.info('\nSubscribe notification active\n{0}'.format(
            29 * '='
        ))
        try:
            for response in self.responses:
                self.log.info(response)
                if self.stopped():
                    self.time_delta = self.stream_max
                    self.log.info("Terminating notification thread")
                    break
                if self.stream_max:
                    t2 = datetime.now()
                    td = t2 - t1
                    self.time_delta = td.seconds
                    if td.seconds > self.stream_max:
                        self.stop()
                        break
                if response.HasField('sync_response'):
                    self.log.info('Subscribe syncing response')
                if response.HasField('update'):
                    self.log.info(
                        '\nSubscribe response:\n{0}\n{1}'.format(
                            19 * '=',
                            str(response)
                        )
                    )
                    self.process_opfields(response)

        except Exception as exc:
            msg = ''
            if hasattr(exc, 'details'):
                msg += 'details: ' + exc.details()
            if hasattr(exc, 'debug_error_string'):
                msg += exc.debug_error_string()
            if not msg:
                msg = str(exc)
            self.result = msg

    def stop(self):
        self.log.info("Stopping notification stream")
        self._stop_event.set()

    def stopped(self):
        return self._stop_event.is_set()


class Gnmi(BaseConnection):
    """Session handling for gNMI connections.

    Can be used with pyATS same as yang.connector.Netconf is used or
    can be used as a standlone module.

    Methods:

    capabilities(): gNMI Capabilities.
    set(dict): gNMI Set.  Input is namespace, xpath/value pairs.
    get(dict): gNMI Get mode='STATE'. Input xpath/value pairs (value optional).
    get_config(dict): gNMI Get mode='CONFIG'. Input xpath/value pairs.
    subscribe(dict): gNMI Subscribe.  Input xpath/value pairs and format
    notify_wait(dict, callback): Notify subscibe thread that event occured, \
        "callback" must be a class with passed, and failed methods and a \
        result class containing "code" property.

    pyATS Examples:

    >>> from pyats.topology import loader
    >>> from yang.connector.gnmi import Gnmi
    >>> testbed=loader.load('testbed_native_test.yaml')
    >>> device=testbed.devices['ddmi-9500-2']
    >>> device.connect(alias='gnmi', via='yang2')
    >>> #####################
    >>> # Set/Get example   #
    >>> #####################
    >>> content={
    ... 'namespace': {'ios: 'http://cisco.com/ns/yang/Cisco-IOS-XE-native',
    ... 'ios-cdp': 'http://cisco.com/ns/yang/Cisco-IOS-XE-cdp'},
    ... 'nodes': [{'xpath': '/ios:native/ios:cdp/ios-cdp:holdtime',
    ... 'value': '10'}]
    ... }
    >>> device.gnmi.set(content)
    []
    >>> content['nodes'][0].pop('value')
    >>> device.gnmi.get(content)
    [{'update': [(10, '/native/cdp/holdtime')]}]
    >>> #####################
    >>> # Capabilities      #
    >>> #####################
    >>> resp=device.gnmi.capabilities()
    >>> resp.keys()
    dict_keys(['supportedModels', 'supportedEncodings', 'gNMIVersion'])

    Standalone Examples (pyATS not installed):

    >>> #####################
    >>> # Capabilities      #
    >>> #####################
    >>> from yang.connector.gnmi import Gnmi
    >>> kwargs={
    ... 'host':'172.23.167.122',
    ... 'port':'50051',
    ... 'root_certificate':'root.pem',
    ... 'username':'admin',
    ... 'password':'C!sco123',
    ... 'ssl_name_override':'ems.cisco.com'
    ... }
    >>> gnmi=Gnmi('iosxe', **kwargs)
    >>> resp = gnmi.capabilities()
    >>> #####################
    >>> # Set example       #
    >>> #####################
    >>> content={
    ... 'namespace': {'ios: 'http://cisco.com/ns/yang/Cisco-IOS-XE-native',
    ... 'ios-cdp': 'http://cisco.com/ns/yang/Cisco-IOS-XE-cdp'},
    ... 'nodes': [{'xpath': '/ios:native/ios:cdp/ios-cdp:holdtime',
    ... 'value': '10'}]
    ... }
    >>> resp = gnmi.set(content)
    >>> #####################
    >>> # Get mode='CONFIG' #
    >>> #####################
    >>> content={
    ... 'namespace': {'ios: 'http://cisco.com/ns/yang/Cisco-IOS-XE-native',
    ... 'ios-cdp': 'http://cisco.com/ns/yang/Cisco-IOS-XE-cdp'},
    ... 'nodes': [{'xpath': '/ios:native/ios:cdp/ios-cdp:holdtime'}]
    ... }
    >>> resp = gnmi.get_config({'content': content, 'returns': returns})
    >>> #####################
    >>> # Get mode='STATE' #
    >>> #####################
    >>> content={
    ... 'namespace': {'ios: 'http://cisco.com/ns/yang/Cisco-IOS-XE-native',
    ... 'ios-cdp': 'http://cisco.com/ns/yang/Cisco-IOS-XE-cdp'},
    ... 'nodes': [{'xpath': '/ios:native/ios:cdp/ios-cdp:holdtime'}]
    ... }
    >>> resp = gnmi.get({'content': content, 'returns': returns})
    >>> #####################
    >>> # Subscribe example #
    >>> #####################
    >>> content={
    ... 'format': {
    ...     'encoding': 'JSON',
    ...     'request_mode': 'STREAM',
    ...     'sample_interval': 5,
    ...     'stream_max': 15,
    ...     'sub_mode': 'SAMPLE'},
    ... }
    >>> # Add namespace, node xpath list similar to Get to the content
    >>> # Add list of expected return values to content
    >>> # Example of an expected return value:
    >>> content['returns']=[{
    ... 'datatype': 'string',
    ... 'id': 0,
    ... 'name': 'name',
    ... 'op': '==',
    ... 'selected': True,
    ... 'value': 'v4acl',
    ... 'xpath': '/acl/acl-sets/acl-set/name'}]
    >>> # Trigger an event that would kick off subscribe
    >>> # Call notify_wait() passing in a callback class (see notify_wait)

   """

    os_class_map = {
        None: None,
        "iosxr": "IOS XR",
        "nxos": "NX-OS",
        "iosxe": "IOS XE",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.device = kwargs.get('device')
        self.channel = None
        dev_args = self.connection_info
        if dev_args.get('protocol', '') != 'gnmi':
            msg = 'Invalid protocol {0}'.format(
                dev_args.get('protocol', '')
            )
            raise TypeError(msg)

        # Initialize ClientBuilder
        self.client_os = self.os_class_map.get(self.device.os, None)
        if self.device.os == 'iosxe':
            self.support_prefix = True
            self.json_ietf = True
        else:
            self.support_prefix = False
            self.json_ietf = False

        # ClientBuilder target is IP:Port
        target = dev_args.get('host') + ':' + str(dev_args.get('port'))
        builder = ClientBuilder(target).set_os(self.client_os)

        # Gather certificate settings
        root = dev_args.get('root_certificate')
        if not root:
            root = None
        if root and os.path.isfile(root):
            root = open(root, 'rb').read()
        chain = dev_args.get('certificate_chain')
        if not chain:
            chain = None
        if chain and os.path.isfile(chain):
            chain = open(chain, 'rb').read()
        private_key = dev_args.get('private_key', '')
        if not private_key:
            private_key = None
        if private_key and os.path.isfile(private_key):
            private_key = open(private_key, 'rb').read()
        if any((root, chain, private_key)):
            builder.set_secure(root, private_key, chain)
            builder.set_ssl_target_override(
                dev_args.get('ssl_name_override', '')
            )
            log.info("Connecting secure channel")
        else:
            builder._set_insecure()
            log.info("Connecting insecure channel")

        # Get/set credentials
        username = dev_args.get('username', '')
        password = dev_args.get('password', '')
        if not username or not password:
            creds = dev_args.get('credentials', '')
            if not creds:
                raise KeyError('No credentials found for testbed')
            if 'gnmi' not in creds:
                log.info('Credentials used from {0}'.format(
                    next(iter(creds))
                ))
            gnmi_uname_pwd = creds.get('')
            if not gnmi_uname_pwd:
                raise KeyError('No credentials found for gNMI')
            username = gnmi_uname_pwd.get('username', '')
            password = gnmi_uname_pwd.get('password', '')
            if not username or not password:
                raise KeyError('No credentials found for gNMI testbed')
            password = to_plaintext(password)
        builder.set_call_authentication(username, password)
        # builder.construct() connects grpc channel and returns client instance
        # builder.construct() in connect() will reset builder object so saving original
        self.original_builder = builder
        self.gnmi = None

    active_notifications = {}

    @property
    def device(self):
        return self._device

    @device.setter
    def device(self, device):
        if device:
            self._device = device

    @property
    def connected(self):
        """Return True if session is connected."""
        return self.gnmi

    def path_elem_to_xpath(self, path_elem, namespace={}, opfields=[]):
        """Convert a Path structure to an Xpath."""
        elems = path_elem.get('elem', [])
        xpath = []
        for elem in elems:
            name = elem.get('name', '')
            if name:
                for mod in namespace.values():
                    name = name.replace(mod + ':', '')
                xpath.append(name)
            key = elem.get('key', '')
            if key:
                for name, value in key.items():
                    for mod in namespace.values():
                        value = str(value).replace(mod + ':', '')
                    opfields.append((
                        value,
                        '/' + '/'.join(xpath) + '/' + name,

                    ))
        return '/' + '/'.join(xpath)

    def get_opfields(self, val, xpath_str, opfields=[], namespace={}):
        if isinstance(val, dict):
            for name, dict_val in val.items():
                opfields = self.get_opfields(
                    dict_val,
                    xpath_str + '/' + name,
                    opfields,
                    namespace
                )
        elif isinstance(val, list):
            for item in val:
                self.get_opfields(item, xpath_str, opfields, namespace)
        else:
            xpath_list = xpath_str.split('/')
            name = xpath_list.pop()
            for mod in namespace.values():
                name = name.replace(mod + ':', '')
            xpath_str = '/'.join(xpath_list)
            opfields.append((val, xpath_str + '/' + name))

        return opfields

    def decode_opfields(self, update={}, namespace={}):
        opfields = []
        xpath_str = self.path_elem_to_xpath(
            update.get('path', {}),
            namespace=namespace,
            opfields=opfields
        )
        if not xpath_str:
            log.error('Xpath not determined from response')
            return []
        # TODO: the val depends on the encoding type
        val = update.get('val', {}).get('jsonIetfVal', '')
        if not val:
            val = update.get('val', {}).get('jsonVal', '')
        if not val:
            log.error('{0} has no values'.format(xpath_str))
            return []
        json_val = base64.b64decode(val).decode('utf-8')
        update_val = json.loads(json_val)
        if not isinstance(update_val, (dict, list)):
            # Just one value returned
            opfields.append((update_val, xpath_str))
            return opfields
        else:
            # Reset opfields to avoid duplicates
            opfields = []
        if isinstance(update_val, dict):
            opfields = self.get_opfields(
                update_val,
                xpath_str,
                opfields,
                namespace
            )
        elif isinstance(update_val, list):
            for val_dict in update_val:
                opfields = self.get_opfields(
                    val_dict,
                    xpath_str,
                    opfields,
                    namespace
                )
        return opfields

    def decode_update(self, update={}, namespace={}):
        """Convert JSON return to python dict for display or processing."""
        val = update.get('val', {}).get('jsonIetfVal', '')
        if not val:
            val = update.get('val', {}).get('jsonVal', '')
        if not val:
            log.error('Update has no value')
            return []
        json_val = base64.b64decode(val).decode('utf-8')
        return json.loads(json_val)

    def decode_notification(self, response, namespace={}):
        """Decode a response from the google.protobuf into a dict."""
        if isinstance(response, dict):
            resp_dict = response
        else:
            resp_dict = json_format.MessageToDict(response)
        notifies = resp_dict.get('notification', [])
        ret_vals = []
        for notify in notifies:
            ret_val = {}
            time_stamp = notify.get('timestamp', '')
            # TODO: convert time_stamp from str nanoseconds since epoch time
            # to datetime
            for update in notify['update']:
                val_dict = self.decode_update(update, namespace=namespace)
                opfields = self.decode_opfields(update, namespace=namespace)
                if 'decode' not in ret_val:
                    ret_val['decode'] = [val_dict]
                else:
                    ret_val['decode'].append(val_dict)
                if 'update' not in ret_val:
                    ret_val['update'] = [opfields]
                else:
                    ret_val['update'].append(opfields)
            deletes = notify.get('delete', [])
            deleted = []
            for delete in deletes:
                xpath_str = self.path_elem_to_xpath(
                    delete.get('path', {}),
                    namespace
                )
                if xpath_str:
                    deleted.append(xpath_str)
            if deleted:
                ret_val['delete'] = deleted
            ret_vals.append(ret_val)
        return ret_vals

    def decode_capabilities(self, caps={}):
        return_caps = {
            'version': 'unknown',
            'encodings': 'unknown',
            'models': []
        }
        if not caps:
            return {}
        caps_dict = json_format.MessageToDict(caps)
        for key, value in caps_dict.items():
            if key == 'gNMIVersion':
                return_caps['version'] = value
            elif key == 'supportedEncodings':
                return_caps['encodings'] = value
            elif key == 'supportedModels':
                return_caps['models'] = value

        return return_caps

    def connect(self):
        # builder.construct() connects grpc channel and returns client
        if self.connected:
            return
        self.builder = copy.deepcopy(self.original_builder)
        self.gnmi, self.channel = self.builder.construct(return_channel=True)
        resp = self.capabilities()
        if resp:
            log.info(
                '\ngNMI version: {0} supported encodings: {1}\n\n'.format(
                    resp.get('gNMIVersion', 'unknown'),
                    resp.get('supportedEncodings', 'unknown')
                ))
            log.info(banner('gNMI CONNECTED'))
        else:
            log.info(banner('gNMI Capabilities not returned'))
            self.disconnect()
            raise gNMIException('Connection not successful')

    def set(self, cmd):
        """Send any Set data command.

        Args:
          cmd (dict): Mapping to namespace, xpath/value. \
              {'namespace': '<prefix>': '<namespace>'}, \
              {'nodes': [{ \
                  'edit-op': '<netconf edit-config operation', \
                  'xpath': '<prefixed Xpath to resource', \
                  'value': <value to set resource to> \
              }]} \
        Returns:
          (dict): gNMI SetResponse
        """
        if not self.connected:
            self.connect()
        try:
            # Convert xpath to path element
            responses = []
            ns, configs, origin = xpath_util.xml_path_to_path_elem(cmd)
            prefix = xpath_util.get_prefix(origin) if self.support_prefix else None
            updates = configs.get('update')
            if len(updates) > 1:
                xpaths = []
                for update in updates:
                    xpath = next(iter(update.keys()))
                    xpaths.append(xpath)
                if os.path.commonprefix(xpaths):
                    updates = xpath_util.get_payload(updates)
            replaces = configs.get('replace')
            if len(replaces) > 1:
                xpaths = []
                for replace in replaces:
                    xpath = next(iter(replace.keys()))
                    xpaths.append(xpath)
                if os.path.commonprefix(xpaths):
                    replaces = xpath_util.get_payload(replaces)

            deletes = configs.get('delete')
            if updates or replaces:
                response = self.gnmi.set_json(
                    updates,
                    replaces,
                    ietf=self.json_ietf,
                    prefix=prefix
                )
                responses.append(response)
            if deletes:
                response = self.gnmi.delete_xpaths(deletes)
                responses.append(response)
            # Do fixup on response
            return responses
        except Exception as exc:
            msg = ''
            msg = exc.details() if hasattr(exc, 'details') else str(exc)
            log.error(banner('ERROR: {0}'.format(msg)))

    def configure(self, cmd):
        return self.set(cmd)

    def get(self, cmd, datatype='STATE'):
        """Send any Get data commmand.

        Args:
          cmd (dict): Mapping to namespace, xpath. \
              {{'namespace': '<prefix>': '<namespace>'}, \
               {'nodes': [{'xpath': '<prefixed Xpath to resource'}]} \
          datatype (str): [ ALL | STATE ] (default: STATE) \
        Returns:
          list: List of dict containing updates, replaces, deletes. \
                Updates and replaces are lists of value/xpath tuples. \
                    [{'updates': [(<value>, <xpath"), ...]}] \
                Deletes are a list of xpaths. \
                    [<xpath>,...] \
        """
        if not self.connected:
            self.connect()
        try:
            # Convert xpath to path element
            ns, msg, origin = xpath_util.xml_path_to_path_elem(
                cmd,
                self.support_prefix
            )
            resp = self.gnmi.get_xpaths(
                msg.get('get', []),
                data_type=datatype
            )
            log.info('\nGNMI response:\n{0}\n{1}'.format(15 * '=', str(resp)))
            # Do fixup on response
            response = self.decode_notification(resp, ns)
            # TODO: Do we need to send back deletes?
            return response
        except Exception as exc:
            msg = ''
            if hasattr(exc, 'details'):
                msg = exc.details()
            else:
                msg = str(exc)
            log.error(banner('ERROR: {0}'.format(msg)))
            return []

    def get_config(self, cmd):
        """Helper function for get.

        Args:
          cmd (dict): See get function.
        Returns:
          list: See get function.
        """
        return self.get(cmd, datatype='CONFIG')

    def execute(self, cmd):
        return self.get(cmd)

    def capabilities(self):
        """Retrieve capabilities from device.

        Returns:
          dict: All capability information.
        """
        if not self.connected:
            self.connect()
        try:
            response = json_format.MessageToDict(self.gnmi.capabilities())
            log.debug('\nDevice capabilities\n{0}{1}'.format(
                19 * '=', str(response))
            )
            return response
        except Exception as exc:
            msg = ''
            msg = exc.details() if hasattr(exc, 'details') else str(exc)
            log.error(banner('ERROR: {0}'.format(msg)))
            return {}

    def subscribe(self, cmd):
        """Subscribe to notification stream.

        Send a subscribe command followed by a "notify_wait()" call.

        The subscribe command sends a request and listens for responses.
        Another command is then executed that would trigger an event.
        Notify wait is then called to inform the notification thread that
        an event was trigger and begin evaluating the returned data against
        expected results.

        Args:
          cmd (dict): Contains:
            'format': { \
              'encoding': [JSON | JSON_IETF], \
              'request_mode': [STREAM | ONCE | POLL], \
              'sample_interval': seconds between sampling, \
              'stream_max': Maximun time to keep stream open in seconds, \
              'sub_mode': [ON_CHANGE | SAMPLE]}, \
            }
            'namespace': same as in get function
            'nodes': same as in get function
            'returns': list of expected data returned in notifications.
                       Example of expected data dict:
                        {'datatype': 'string',
                            'name': 'name',
                            'op': '==',
                            'selected': True,
                            'value': 'v4acl',
                            'xpath': '/acl/acl-sets/acl-set/name'}

        """
        if not self.connected:
            self.connect()
        try:
            # Convert xpath to path element
            ns, msg, origin = xpath_util.xml_path_to_path_elem(cmd)
            prefix = xpath_util.get_prefix(origin) if self.support_prefix else None
            format = cmd['format']
            subscribe_xpaths = msg['get']
            subscribe_response = self.gnmi.subscribe_xpaths(
                subscribe_xpaths,
                format.get('request_mode', 'STREAM'),
                format.get('sub_mode', 'SAMPLE'),
                format.get('encoding', 'JSON_IETF'),
                self.gnmi._NS_IN_S * format.get('sample_interval', 10),
                prefix=prefix
            )
            if format.get('request_mode', 'STREAM') == 'ONCE':
                # Do fixup in response
                response_verify = cmd.get('verifier')
                returns = cmd.get('returns')
                for response in subscribe_response:
                    if response.HasField('update'):
                        log.info("GNMI response:\n==============\n{}".format(response))
                        resp = json_format.MessageToDict(response)
                        update = resp.get('update')
                        updates = update.get('update')
                        opfields = self.decode_opfields(
                            updates[0] if isinstance(updates, list) else updates,
                            ns
                        )
                        return response_verify(opfields, returns)
                    return False
            else:
                cmd['namespace'] = ns
                cmd['decode'] = self.decode_opfields
                subscribe_thread = GnmiNotification(
                    self,
                    subscribe_response,
                    **cmd
                )
                subscribe_thread.start()
                self.active_notifications[self] = subscribe_thread
                if cmd['format']['request_mode'] == 'ON_CHANGE':
                    subscribe_thread.event_triggered = True
                return True
        except Exception as exc:
            msg = ''
            msg = exc.details() if hasattr(exc, 'details') else str(exc)
            log.error(banner('ERROR: {0}'.format(msg)))

    def notify_wait(self, steps):
        """Activate notification thread and check results."""
        notifier = self.active_notifications.get(self)
        if notifier:
            if steps.result.code != 1:
                notifier.stop()
                del self.active_notifications[self]
                return
            notifier.event_triggered = True
            log.info(banner('NOTIFICATION EVENT TRIGGERED'))
            wait_for_sample = notifier.sample_interval - 1
            cntr = 1.0
            while cntr < float(notifier.stream_max):
                log.info('Listening for notifications from subscribe stream, {} seconds elapsed'.format(
                    cntr)
                )
                cntr += 1
                if notifier.result is not None and wait_for_sample <= 0:
                    notifier.stop()
                    if notifier.result is True:
                        steps.passed(
                            '\n' + banner('NOTIFICATION RESPONSE PASSED')
                        )
                    else:
                        steps.failed(
                            '\n' + banner('NOTIFICATION RESPONSE FAILED')
                        )
                    break
                sleep(1)
                wait_for_sample -= 1
            else:
                notifier.stop()
                steps.failed('\n' + banner('STREAM TIMED OUT WITHOUT RESPONSE'))

            if self in self.active_notifications:
                del self.active_notifications[self]

    def get_updates(self, response):
        """Notification check."""
        return self.decode_response(response)

    def disconnect(self):
        """Disconnect from SSH device."""
        if self.connected:
            if self.channel:
                self.channel.close()
            self.gnmi = None
            del self.channel

    def __enter__(self):
        """Establish a session using a Context Manager."""
        if not self.connected:
            self.connect()
        return self

    def __exit__(self, *args):
        """Gracefully close connection on Context Manager exit."""
        self.disconnect()
