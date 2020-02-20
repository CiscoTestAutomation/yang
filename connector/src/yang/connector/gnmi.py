import traceback
import os
import logging
from collections import OrderedDict, Iterable
import base64
import json
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


class Gnmi(BaseConnection):
    """Session handling for gNMI connections."""

    os_class_map = {
        None: None,
        "iosxr": "IOS XR",
        "nexus": "NX-OS",
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
        import pdb; pdb.set_trace()
        self.client_os = self.os_class_map.get(device.os, None)
        # ClientBuilder target is IP:Port
        target = dev_args.get('host') + ':' + str(dev_args.get('port'))
        builder = ClientBuilder(target).set_os(self.client_os)
        # Gather certificate settings
        root = dev_args.get('root_certificate', '')
        if os.path.isfile(root):
            root = open(root, 'rb').read()
        chain = dev_args.get('certificate_chain', '')
        if os.path.isfile(chain):
            chain = open(chain, 'rb').read()
        private_key = dev_args.get('private_key', '')
        if os.path.isfile(private_key):
            private_key= open(private_key, 'rb').read()
        builder.set_secure(root, private_key, chain)
        builder.set_ssl_target_override(
            dev_args.get('ssl_name_override', None)
        )
        builder.set_call_authentication(
            dev_args.get('username'),
            dev_args.get('password')
        )
        # builder.construct() returns client and connects the channel
        self.builder = builder
        log.info('GNMI builder ready')
        self.gnmi = None

    @property
    def connected(self):
        """Return True if session is connected."""
        return self.gnmi

    def get_prefix(self, xpaths, prefix=[]):
        """Return shortest common prefix for multiple xpaths."""
        if not isinstance(xpaths, Iterable) or not xpaths:
            # Done so lets return the prefix path
            prefix = '/'.join([t[1] for t in prefix if t[1]])
            if prefix:
                prefix = '/' + prefix
            return prefix
        if not prefix:
            prefix = xpath_tokenizer_re.findall(xpaths[0])
            return self.get_prefix(xpaths[1:], prefix)
        else:
            for i, t in enumerate(xpath_tokenizer_re.findall(xpaths[0])):
                if len(prefix) <= i:
                    # Same prefix so move on to next Xpath
                    return self.get_prefix(xpaths[1:], prefix)
                if prefix[i] != t:
                    # End of matching Xpath tokens
                    prefix = prefix[:i]
                    if len(prefix) <= 1:
                        # Found Xpath with no common prefix so bail out
                        return self.get_prefix([], [])
                    else:
                        # Move on to next Xpath
                        return self.get_prefix(xpaths[1:], prefix)
            # Prefix matched so move on to next Xpath
            return self.get_prefix(xpaths[1:], prefix)

    def xpath_to_path_elem(self, request):
        paths = []
        config = {
            'update': [],
            'replace': [],
            'delete': []
        }
        if 'nodes' not in request:
            # TODO: raw rpc?
            return paths
        else:
            namespace_modules = {}
            for prefix, nspace in request.get('namespace', {}).items():
                module = ''
                if '/Cisco-IOS-' in nspace:
                    module = nspace[nspace.rfind('/') + 1:]
                elif '/openconfig.net' in nspace:
                    module = 'openconfig-'
                    module += nspace[nspace.rfind('/') + 1:]
                elif 'urn:ietf:params:xml:ns:yang:' in nspace:
                    module = nspace.replace(
                        'urn:ietf:params:xml:ns:yang:', '')
                if module:
                    namespace_modules[prefix] = module
            for node in request.get('nodes', []):
                if 'xpath' not in node:
                    log.error('Xpath is not in message')
                else:
                    xpath = node['xpath']
                    value = node.get('value', '')
                    edit_op = node.get('edit-op', '')

                    for pfx, ns in namespace_modules.items():
                        xpath = xpath.replace(pfx + ':', ns + ':')
                        value = value.replace(pfx + ':', ns + ':')
                    if value or edit_op:
                        if edit_op in ['create', 'merge', 'replace']:
                            xpath_lst = xpath.split('/')
                            name = xpath_lst.pop()
                            xpath = '/'.join(xpath_lst)
                            if edit_op == 'replace':
                                if not config['replace']:
                                    config['replace'] = [{
                                        xpath: {name: value}
                                    }]
                                else:
                                    config['replace'].append(
                                        {xpath: {name: value}}
                                    )
                            else:
                                if not config['update']:
                                    config['update'] = [{
                                        xpath: {name: value}
                                    }]
                                else:
                                    config['update'].append(
                                        {xpath: {name: value}}
                                    )
                        elif edit_op in ['delete', 'remove']:
                            if config['delete']:
                                config['delete'].add(xpath)
                            else:
                                config['delete'] = set(xpath)
                    else:
                        paths.append(
                            self.gnmi.parse_xpath_to_gnmi_path(xpath)
                        )

        return paths, namespace_modules, config

    def path_elem_to_xpath(self, path_elem, namespace):
        """Convert a Path structure to an Xpath."""
        elems = path_elem.get('elem', [])
        xpath = []
        for elem in elems:
            name = elem.get('name', '')
            if name:
                for mod in namespace.values():
                    name = name.replace(mod + ':', '')
                xpath.append(name)
        return '/' + '/'.join(xpath)

    def decode_response(self, response, namespace):
        """Decode a response from the google.protobuf into a dict."""
        resp_dict = json_format.MessageToDict(response)
        notifies = resp_dict.get('notification', [])
        ret_vals = []
        for notify in notifies:
            time_stamp = notify.get('timestamp', '')
            # TODO: convert time_stamp from str nanoseconds since epoch time
            # to datetime
            updates = notify.get('update', [])
            ret_val = {'time_stamp': time_stamp}
            for update in updates:
                opfields = []
                xpath_str = self.path_elem_to_xpath(
                    update.get('path', {}),
                    namespace
                )
                if not xpath_str:
                    log.error('Xpath not determined from response')
                    continue
                val = update.get('val', {}).get('jsonIetfVal', '')
                if not val:
                    log.error('{0} has no values'.format(xpath_str))
                    continue
                json_val = base64.b64decode(val).decode('utf-8')
                val_dict = json.loads(json_val)
                # MessageToDict does not decode all values as strings
                for name, value in val_dict.items():
                    opfields.append({
                        'xpath': xpath_str + '/' + name,
                        'value': str(value)
                    })
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
            import pdb; pdb.set_trace()
            responses = []
            paths, ns, configs = self.xpath_to_path_elem(cmd)
            updates = configs.get('update')
            replaces = configs.get('replace')
            deletes = configs.get('delete')
            if updates or replaces:
                if hasattr(self.gnmi, 'set_json'):
                    responses.append(self.gnmi.set_json(
                        updates,
                        replaces,
                    ))
            if deletes:
                responses.append(self.gnmi.delete_xpaths(deletes))
            # Do fixup on response
            return responses
        except Exception as exe:
            log.error(banner('{0}: {1}'.format(exe.code(), exe.details())))

    def configure(self, cmd):
        return self.set(cmd)

    def get(self, cmd):
        """Send any Get data commmand.

        Args:
          cmd (str): Configuration CLI command.
        Returns:
          (str): CLI response
        """
        if not self.connected:
            self.connect()
        try:
            import pdb; pdb.set_trace()
            # Convert xpath to path element
            request, ns, configs = self.xpath_to_path_elem(cmd)
            resp = self.gnmi.get(request)
            # Do fixup on response
            response = self.decode_response(resp, ns)
            return response
        except Exception as exe:
            log.error(banner('{0}: {1}'.format(exe.code(), exe.details())))
            return []

    def execute(self, cmd):
        return self.get(cmd)


    def capabilities(self, request):
        """Retrieve capabilities from device."""
        if not self.connected:
            self.connect()
        try:
            return self.gnmi.capabilities()
        except Exception as exe:
            log.error(banner('{0}: {1}'.format(exe.code(), exe.details())))

    def subscribe(self, cmd):
        """Subscribe to notification stream."""
        if not self.connected:
            self.connect()
        try:
            # Convert xpath to path element
            request = self.xpath_to_path_elem(cmd)
            resp = self.gnmi.subscribe(request)
            # Do fixup in response
            return resp
        except Exception as exe:
            log.error(banner('{0}: {1}'.format(exe.code(), exe.details())))

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
