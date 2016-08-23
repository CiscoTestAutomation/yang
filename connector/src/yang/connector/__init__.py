"""yang.connector module defines a set of classes that connect to Data Model
Interfaces (DMI), in particular, an implementation of Netconf client. Restconf
implementation is coming next."""

# metadata
__version__ = '2.0.0'
__author__ = ('Jonathan Yang <yuekyang@cisco.com>',
              'Siming Yuan <siyuan@cisco.com',)
__contact__ = 'yang-python@cisco.com'
__copyright__ = 'Cisco Systems, Inc. Cisco Confidential'


import re
import logging
from ncclient import manager
from ncclient import operations
from ncclient import transport

from ncclient.devices.default import DefaultDeviceHandler

from ats.connections import BaseConnection

# create a logger for this module
logger = logging.getLogger(__name__)

class Netconf(manager.Manager, BaseConnection):

    def __init__(self, *args, **kwargs):

        # instanciate BaseConnection
        # (could use super...)
        BaseConnection.__init__(self, *args, **kwargs)

        # shortwire Ncclient device handling portion
        # and create just the DeviceHandler
        device_handler = DefaultDeviceHandler()

        # create the session instance
        session = transport.SSHSession(device_handler)

        # load known_hosts file (if available)
        session.load_known_hosts()

        # instanciate ncclient Manager
        # (can't use super due to mro change)
        manager.Manager.__init__(self, session = session,
                                       device_handler = device_handler, 
                                       *args, **kwargs)

    @property
    def session(self):
        return self._session
    
    def connect(self):

        # get all connection information (dupe it)
        connection_info = self.connection_info.copy()
        # rename ip -> host, cast to str type
        connection_info['host'] = str(connection_info.pop('ip'))
        # remove class
        connection_info.pop('class')

        try:
            self.session.connect(**connection_info)
        except Exception:
            if self.session.transport:
                self.session.close()
            raise

        # documentation for connect() from SSHSession
        # -------------------------------------------
        # def connect(self, host, port=830, timeout=None, 
        #                unknown_host_cb=default_unknown_host_cb,
        #                username=None, password=None, key_filename=None, allow_agent=True,
        #                hostkey_verify=True, look_for_keys=True, ssh_config=None):

        #        """Connect via SSH and initialize the NETCONF session. First attempts the publickey authentication method and then password authentication.

        #        To disable attempting publickey authentication altogether, call with *allow_agent* and *look_for_keys* as `False`.

        #        *host* is the hostname or IP address to connect to

        #        *port* is by default 830, but some devices use the default SSH port of 22 so this may need to be specified

        #        *timeout* is an optional timeout for socket connect

        #        *unknown_host_cb* is called when the server host key is not recognized. It takes two arguments, the hostname and the fingerprint (see the signature of :func:`default_unknown_host_cb`)

        #        *username* is the username to use for SSH authentication

        #        *password* is the password used if using password authentication, or the passphrase to use for unlocking keys that require it

        #        *key_filename* is a filename where a the private key to be used can be found

        #        *allow_agent* enables querying SSH agent (if found) for keys

        #        *hostkey_verify* enables hostkey verification from ~/.ssh/known_hosts

        #        *look_for_keys* enables looking in the usual locations for ssh keys (e.g. :file:`~/.ssh/id_*`)

        #        *ssh_config* enables parsing of an OpenSSH configuration file, if set to its path, e.g. :file:`~/.ssh/config` or to True (in this case, use :file:`~/.ssh/config`).
        #        """
        #        # Optionaly, parse .ssh/config


    def disconnect(self):
        self.session.close()

    def execute(self, operation, *args, **kwargs):

        # allow for operation string type
        if type(operation) is str:
            try:
                cls = manager.OPERATIONS[operation]
            except KeyError:
                raise ValueError("No such operation '%s'. \n"
                                 "Supported operations: %s" 
                                 % (operation, list(manager.OPERATIONS.keys())))
        else:
            cls = operation

        return super().execute(cls, *args, **kwargs)

    def request(self, msg, timeout=10):

        rpc = RawRPC(session = self.session, 
                     device_handler = self._device_handler,
                     timeout = timeout)
        return rpc.request(msg)


class RawRPC(operations.rpc.RPC):

    def _wrap(self, op):
        return re.sub(r'message-id="([A-Za-z0-9_\-:]+)"',
                    r'message-id="%s"' % self._id, 
                    op)

    def request(self, op):
        return self._request(op).xml