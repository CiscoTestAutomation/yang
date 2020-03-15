import traceback
import os
import logging
from collections import OrderedDict, Iterable
import base64
import json
from threading import Thread
from time import sleep
from datetime import datetime
from xml.etree.ElementPath import xpath_tokenizer_re

from google.protobuf import json_format

from cisco_gnmi import ClientBuilder

from pyats.log.utils import banner
from pyats.connections import BaseConnection
from pyats.utils.secret_strings import to_plaintext

# try to record usage statistics
#  - only internal cisco users will have stats.CesMonitor module
#  - below code does nothing for DevNet users -  we DO NOT track usage stats
#    for PyPI/public/customer users
try:
    # new internal cisco-only pkg since devnet release
    from ats.cisco.stats import CesMonitor
except Exception:
    try:
        # legacy pyats version, stats was inside utils module
        from ats.utils.stats import CesMonitor
    except Exception:
        CesMonitor = None
finally:
    if CesMonitor is not None:
        # CesMonitor exists -> this is an internal cisco user
        CesMonitor(action = __name__, application='pyATS Packages').post()


# create a logger for this module
log = logging.getLogger(__name__)


class GnmiNotification(Thread):
        """Thread listening for event notifications from the device."""

        def __init__(self, device, response, **request):
            Thread.__init__(self)
            self.device = device
            self.terminate = False
            self.log = logging.getLogger(__name__)
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

        def process_opfields(self, response):
            subscribe_resp = json_format.MessageToDict(response)
            updates = subscribe_resp['update']
            resp = self.decode_response(updates)
            if resp:
                self.response_verify(resp, self.returns.copy())
            else:
                self.log.error('No values in subscribe response')

        def run(self):
            """Check for inbound notifications."""
            self.log.info("Starting notification thread")
            t1 = datetime.now()
            while not self.terminate:
                self.log.info('Subscribe active')
                for response in self.responses:
                    if response.HasField('sync_response'):
                        self.log.info('Subscribe syncing response')
                    if response.HasField('update'):
                        self.log.info(
                            'Subscribe response {0}'.format(
                                str(response)
                            )
                        )
                        self.process_opfields(response)
                        self.log.info('Subscribe opfields processed')
                    if self.stream_max:
                        t2 = datetime.now()
                        td = t2 - t1
                        self.log.info(
                            'Subscribe time {0} seconds'.format(td.seconds)
                        )
                        if td.seconds > self.stream_max:
                            self.terminate = True
                            break

            self.log.info("Terminating notification thread")


class Gnmi(BaseConnection):
    """Session handling for gNMI connections."""

    os_class_map = {
        None: None,
        "iosxr": "IOS XR",
        # TODO: nxos cisco-gnmi support is not ready so use iosxe
        "nxos": "NX-OS",
        # "nxos": "IOS XE",
        "iosxe": "IOS XE",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        device = kwargs.get('device')
        dev_args = self.connection_info
        if dev_args.get('protocol', '') != 'gnmi':
            # TODO: what now?
            return
        # Initialize ClientBuilder
        self.client_os = self.os_class_map.get(device.os, None)
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
            private_key= open(private_key, 'rb').read()
        builder.set_secure(root, private_key, chain)
        builder.set_ssl_target_override(
            dev_args.get('ssl_name_override', '')
        )
        builder.set_call_authentication(
            dev_args.get('username'),
            dev_args.get('password')
        )
        # builder.construct() returns client and connects the channel
        self.builder = builder
        self.gnmi = self.builder.construct()
        log.info(banner('gNMI CONNECTED'))

    @property
    def connected(self):
        """Return True if session is connected."""
        return self.gnmi

    def path_elem_to_xpath(self, path_elem, namespace={}, opfields=[]):
        """Convert a Path structure to an Xpath."""
        elems = path_elem.get('elem', [])
        xpath = []
        keys = []
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

    def get_opfields(self, val, xpath_str, opfields=[]):
        if isinstance(val, dict):
            for name, dict_val in val.items():
                opfields = self.get_opfields(
                    dict_val,
                    xpath_str + '/' + name,
                    opfields=opfields
                )
            return opfields
        elif isinstance(val, list):
            for item in val:
                for name, dict_val in item.items():
                    opfields = self.get_opfields(
                        dict_val,
                        xpath_str + '/' + name,
                        opfields
                    )
            return opfields
        else:
            xpath_list = xpath_str.split('/')
            name = xpath_list.pop()
            xpath_str = '/'.join(xpath_list)
            opfields.append((val, xpath_str + '/' + name))
            return opfields

    def decode_update(self, updates=[]):
        opfields=[]
        for update in updates['update']:
            xpath_str = self.path_elem_to_xpath(
                update.get('path', {}),
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
            if isinstance(update_val, dict):
                update_val = [update_val]
            for val_dict in update_val:
                opfields = self.get_opfields(
                    val_dict,
                    xpath_str,
                    opfields
                )
        return opfields

    def decode_notification(self, response, namespace):
        """Decode a response from the google.protobuf into a dict."""
        resp_dict = json_format.MessageToDict(response)
        notifies = resp_dict.get('notification', [])
        ret_vals = []
        for notify in notifies:
            ret_val = {}
            time_stamp = notify.get('timestamp', '')
            # TODO: convert time_stamp from str nanoseconds since epoch time
            # to datetime
            opfields = self.decode_update(notify)
            ret_val['update'] = opfields
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

    def set(self, cmd):
        """Send any Set data command.

        Args:
          cmd (str): Configuration gNMI command.
        Returns:
          (str): CLI response
        """
        if not self.connected:
            self.connect()
        try:
            # Convert xpath to path element
            responses = []
            ns, configs, origin = self.gnmi.xpath_to_path_elem(cmd)
            updates = configs.get('update')
            replaces = configs.get('replace')
            deletes = configs.get('delete')
            if updates or replaces:
                responses.append(
                    self.gnmi.set_json(
                        updates,
                        replaces,
                        origin=origin
                    ))
            if deletes:
                responses.append(self.gnmi.delete_xpaths(deletes))
            # Do fixup on response
            return responses
        except Exception as exe:
            log.error(banner('{0}: {1}'.format(exe.code(), exe.details())))

    def configure(self, cmd):
        return self.set(cmd)

    def get(self, cmd, datatype='STATE'):
        """Send any Get data commmand.

        Args:
          cmd (str): Configuration CLI command.
          datatype (str): [ ALL | STATE ] (default: STATE)
        Returns:
          (str): CLI response
        """
        if not self.connected:
            self.connect()
        try:
            # Convert xpath to path element
            ns, msg, origin = self.gnmi.xpath_to_path_elem(cmd)
            resp = self.gnmi.get_xpaths(
                msg.get('get', []),
                data_type=datatype,
                origin=origin
            )
            log.info(str(resp))
            # Do fixup on response
            response = self.decode_notification(resp, ns)
            # TODO: Do we need to send back deletes?
            return response
        except Exception as exe:
            log.error(banner('{0}: {1}'.format(exe.code(), exe.details())))
            return []

    def get_config(self, cmd):
        """Send any get-config data commmand.

        Args:
          cmd (str): Configuration CLI command.
        Returns:
          (str): CLI response
        """
        return self.get(cmd, datatype='ALL')

    def execute(self, cmd):
        return self.get(cmd)

    def capabilities(self):
        """Retrieve capabilities from device."""
        if not self.connected:
            self.connect()
        try:
            response = json_format.MessageToDict(self.gnmi.capabilities())
            return response
        except Exception as exe:
            log.error(banner('{0}: {1}'.format(exe.code(), exe.details())))
            return {}

    def subscribe(self, cmd):
        """Subscribe to notification stream."""
        if not self.connected:
            self.connect()
        try:
            # Convert xpath to path element
            ns, msg, origin = self.gnmi.xpath_to_path_elem(cmd)
            format = cmd['format']
            subscribe_xpaths = msg['get']
            subscribe_response = self.gnmi.subscribe_xpaths(
                subscribe_xpaths,
                format.get('request_mode', 'STREAM'),
                format.get('sub_mode', 'SAMPLE'),
                format.get('encoding', 'PROTO'),
                self.gnmi._NS_IN_S * cmd.get('sample_interval', 10),
                origin
            )
            if format.get('request_mode', 'STREAM') == 'ONCE':
                # Do fixup in response
                response_verify = cmd.get('verifier')
                returns = cmd.get('returns')
                for response in subscribe_response:
                    if response.HasField('sync_response'):
                        print('timestamp here')
                    if response.HasField('update'):
                        resp = json_format.MessageToDict(response)
                        update = resp.get('update')
                        ret_val = {'timestamp': update.get('timestamp')}
                        opfields = self.decode_update(
                            update.get('update')
                        )
                        return response_verify(opfields, returns)
                    return False
            else:
                cmd['namespace'] = ns
                cmd['decode'] = self.decode_update
                subscribe_thread = GnmiNotification(
                    self,
                    subscribe_response,
                    **cmd
                )
                subscribe_thread.start()
                return True
        except Exception as exe:
            log.error(banner('{0}: {1}'.format(exe.code(), exe.details())))

    def get_updates(self, response):
        """Notification check."""
        return self.decode_response(response)

    def connect(self):
        """Connect to gRPC device."""
        # - Certificates bind domain name, server name, or host name to
        #   organization identity (company name/location)
        # - self.__root_certificates - Global authority root issuer
        # - self.__private_key - used to decrypt (public key encrypts)
        # - self.__certificate_chain - List of issuers with root being final
        #   authority
        if not self.gnmi:
            self.gnmi = self.builder.construct()
            log.info(banner('gNMI CONNECTED'))

    def disconnect(self):
        """Disconnect from SSH device."""
        if self.connected:
            self.gnmi = None
            self.builder._reset()

    def __enter__(self):
        """Establish a session using a Context Manager."""
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Gracefully close connection on Context Manager exit."""
        self.disconnect()
