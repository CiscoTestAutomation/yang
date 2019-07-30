"""yang.connector module defines a set of classes that connect to Data Model
Interfaces (DMI), in particular, an implementation of Netconf client by
wrapping up ncclient package. Restconf implementation is coming next."""

# metadata
__version__ = '19.7'
__author__ = ('Jonathan Yang <yuekyang@cisco.com>',
              'Siming Yuan <siyuan@cisco.com',
              'Myles Dear <mdear@cisco.com',)
__contact__ = 'yang-python@cisco.com'
__copyright__ = 'Cisco Systems, Inc.'


import re
import time
import atexit
import logging
from ncclient import manager
from ncclient import operations
from ncclient import transport
from ncclient.devices.default import DefaultDeviceHandler
from ncclient.operations.errors import TimeoutExpiredError

try:
    from pyats.connections import BaseConnection
except ImportError:
    try:
        from ats.connections import BaseConnection
    except ImportError:
        raise ImportError('Cannot import pyATS - make sure pyATS is installed ' 
                          'in your environment') from None
try:
    from pyats.utils.secret_strings import to_plaintext
except ImportError:
    def to_plaintext(string):
        return(str(string))

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
logger = logging.getLogger(__name__)

class Netconf(manager.Manager, BaseConnection):
    '''Netconf

    Implementation of NetConf connection to devices (NX-OS, IOS-XR or IOS-XE),
    based on pyATS BaseConnection and ncclient.

    YAML Example::

        devices:
            asr22:
                type: 'ASR'
                tacacs:
                    login_prompt: "login:"
                    password_prompt: "Password:"
                    username: "admin"
                passwords:
                    tacacs: admin
                    enable: admin
                    line: admin
                connections:
                    a:
                        protocol: telnet
                        ip: "1.2.3.4"
                        port: 2004
                    vty:
                        protocol : telnet
                        ip : "2.3.4.5"
                    netconf:
                        class: yang.connector.Netconf
                        ip : "2.3.4.5"
                        port: 830
                        username: admin
                        password: admin

    Code Example::

        >>> from pyats.topology import loader
        >>> testbed = loader.load('/users/xxx/xxx/asr22.yaml')
        >>> device = testbed.devices['asr22']
        >>> device.connect(alias='nc', via='netconf')
        >>> device.nc.connected
        True
        >>> netconf_request = """
        ...     <rpc message-id="101"
        ...      xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
        ...     <get>
        ...     <filter>
        ...     <native xmlns="http://cisco.com/ns/yang/ned/ios">
        ...     <version>
        ...     </version>
        ...     </native>
        ...     </filter>
        ...     </get>
        ...     </rpc>
        ...     """
        >>> reply = device.nc.request(netconf_request)
        >>> print(reply)
        <?xml version="1.0" encoding="UTF-8"?>
        <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"
        message-id="101"><data>
        <native xmlns="http://cisco.com/ns/yang/ned/ios">
        <version>16.3</version></native></data></rpc-reply>
        >>> device.nc.disconnect()
        >>> device.nc.connected
        False
        >>>

    Attributes
    ----------
    timeout : `int`
        Timeout value in seconds which is used by paramiko channel. By
        default this value is 30 seconds.

    client_capabilities : `object`
        Object ncclient.capabilities.Capabilities representing the client's
        capabilities.

    server_capabilities : `object`
        Object ncclient.capabilities.Capabilities representing the server's
        capabilities, and it has a list of data models the server supports.

    async_mode : `boolean`
        Specify whether operations are executed asynchronously (True) or
        synchronously (False). The default value is False.
    '''

    def __init__(self, *args, **kwargs):
        '''
        __init__ instantiates a single connection instance.
        '''
        # set defaults
        kwargs.setdefault('timeout', 30)

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
                                       timeout = self.timeout)

    @property
    def session(self):
        '''session

        High-level api: return the SSH session object.

        Returns
        -------

        object
            The SSH session that was created by ncclient.transport.SSHSession.
        '''

        return self._session

    def connect(self):
        '''connect

        High-level api: opens the NetConf connection and exchanges
        capabilities. Since topology YAML file is parsed by BaseConnection,
        the following parameters can be specified in your YAML file.

        Parameters
        ----------

        host : `string`
            Hostname or IP address to connect to.
        port : `int`, optional
            By default port is 830, but some devices use the default SSH port
            of 22 so this may need to be specified.
        timeout : `int`, optional
            An optional keyed argument to set timeout value in seconds. By
            default this value is 30 seconds.
        username : `string`
            The username to use for SSH authentication.
        password : `string`
            The password used if using password authentication, or the
            passphrase to use for unlocking keys that require it.
        key_filename : `string`
            a filename where a the private key to be used can be found.
        allow_agent : `boolean`
            Enables querying SSH agent (if found) for keys. The default value
            is True.
        hostkey_verify : `boolean`
            Enables hostkey verification from ~/.ssh/known_hosts. The default
            value is False.
        look_for_keys : `boolean`
            Enables looking in the usual locations for ssh keys
            (e.g. ~/.ssh/id_*). The default value is True.
        ssh_config : `string`
            Enables parsing of an OpenSSH configuration file, if set to its
            path, e.g. ~/.ssh/config or to True. If the value is True,
            ncclient uses ~/.ssh/config. The default value is None.

        Raises
        ------

        Exception
            If the YAML file does not have correct connections section, or
            establishing transport to ip:port is failed, ssh authentication is
            failed, or other transport failures.

        Note
        ----

        There is no return from this method. If something goes wrong, an
        exception will be raised.


        YAML Example::

            devices:
                asr22:
                    type: 'ASR'
                    tacacs:
                        login_prompt: "login:"
                        password_prompt: "Password:"
                        username: "admin"
                    passwords:
                        tacacs: admin
                        enable: admin
                        line: admin
                    connections:
                        a:
                            protocol: telnet
                            ip: "1.2.3.4"
                            port: 2004
                        vty:
                            protocol : telnet
                            ip : "2.3.4.5"
                        netconf:
                            class: yang.connector.Netconf
                            ip : "2.3.4.5"
                            port: 830
                            username: admin
                            password: admin

        Code Example::

            >>> from pyats.topology import loader
            >>> testbed = loader.load('/users/xxx/xxx/asr22.yaml')
            >>> device = testbed.devices['asr22']
            >>> device.connect(alias='nc', via='netconf')
            >>>

        Expected Results::

            >>> device.nc.connected
            True
            >>> for iter in device.nc.server_capabilities:
            ...     print(iter)
            ...
            urn:ietf:params:xml:ns:yang:smiv2:RFC-1215?module=RFC-1215
            urn:ietf:params:xml:ns:yang:smiv2:SNMPv2-TC?module=SNMPv2-TC
            ...
            >>>
        '''

        if self.connected:
            return

        logger.debug(self.session)
        if not self.session.is_alive():
            self._session = transport.SSHSession(self._device_handler)

        # default values
        defaults = {
            'host': None,
            'port': 830,
            'timeout': 30,
            'username': None,
            'password': None,
            'key_filename': None,
            'allow_agent': False,
            'hostkey_verify': False,
            'look_for_keys': False,
            'ssh_config': None,
            }
        defaults.update(self.connection_info)

        # remove items
        disregards = ['class', 'model', 'protocol', 
                      'async_mode', 'raise_mode', 'credentials']
        defaults = {k: v for k, v in defaults.items() if k not in disregards}

        # rename ip -> host, cast to str type
        if 'ip' in defaults:
            defaults['host'] = str(defaults.pop('ip'))

        # rename user -> username
        if 'user' in defaults:
            defaults['username'] = str(defaults.pop('user'))

        # check credentials
        if self.connection_info.get('credentials'):
            try:
                defaults['username'] = str(self.connection_info['credentials']['netconf']['username'])
            except Exception:
                pass
            try:
                defaults['password'] = to_plaintext(self.connection_info['credentials']['netconf']['password'])
            except Exception:
                pass

        defaults = {k: getattr(self, k, v) for k, v in defaults.items()}

        try:
            self.session.connect(**defaults)
        except Exception:
            if self.session.transport:
                self.session.close()
            raise

        @atexit.register
        def cleanup():
            if self.session.transport:
                self.session.close()

    def disconnect(self):
        '''disconnect

        High-level api: closes the NetConf connection.
        '''

        self.session.close()

    def configure(self, msg):
        '''configure

        High-level api: configure is a common method of console, vty and ssh
        sessions, however it is not supported by this Netconf class. This is
        just a placeholder in case someone mistakenly calls config method in a
        netconf session. An Exception is thrown out with explanation.

        Parameters
        ----------

        msg : `str`
            Any config CLI need to be sent out.

        Raises
        ------

        Exception
            configure is not a supported method of this Netconf class.
        '''

        raise Exception('configure is not a supported method of this Netconf '
                        'class, since a more suitable method, edit_config, is '
                        'recommended. There are nine netconf operations '
                        'defined by RFC 6241, and edit-config is one of them. '
                        'Also users can build any netconf requst, including '
                        'invalid netconf requst as negative test cases, in '
                        'XML format and send it by method request.')

    def execute(self, operation, *args, **kwargs):
        '''execute

        High-level api: The fact that most connection classes implement
        execute method lead us to add this method here as well.
        Supported operations are get, get_config, get_schema, dispatch,
        edit_config, copy_config, validate, commit, discard_changes,
        delete_config, lock, unlock, close_session, kill_session,
        poweroff_machine and reboot_machine. Refer to ncclient document for
        more details.
        '''

        # allow for operation string type
        if type(operation) is str:
            try:
                cls = manager.OPERATIONS[operation]
            except KeyError:
                raise ValueError('No such operation "%s".\n'
                                 'Supported operations are: %s' %
                                 (operation, list(manager.OPERATIONS.keys())))
        else:
            cls = operation

        return super().execute(cls, *args, **kwargs)

    def request(self, msg, timeout=30):
        '''request

        High-level api: sends message through NetConf session and returns with
        a reply. Exception is thrown out either the reply is in wrong
        format or timout. Users can modify timeout value (in seconds) by
        passing parameter timeout. Users may want to set a larger timeout when
        making a large query.

        Parameters
        ----------

        msg : `str`
            Any message need to be sent out in XML format. The message can be
            in wrong format if it is a negative test case. Because ncclient
            tracks same message-id in both rpc and rpc-reply, missing
            message-id in your rpc may cause exception when receiving
            rpc-reply. Most other wrong format rpc's can be sent without
            exception.
        timeout : `int`, optional
            An optional keyed argument to set timeout value in seconds. Its
            default value is 30 seconds.

        Returns
        -------

        str
            The reply from the device in string. If something goes wrong, an
            exception will be raised.


        Raises
        ------

        Exception
            If NetConf is not connected, or there is a timeout when receiving
            reply.


        Code Example::

            >>> from pyats.topology import loader
            >>> testbed = loader.load('/users/xxx/xxx/asr_20_22.yaml')
            >>> device = testbed.devices['asr22']
            >>> device.connect(alias='nc', via='netconf')
            >>> netconf_request = """
            ...     <rpc message-id="101"
            ...      xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
            ...     <get>
            ...     <filter>
            ...     <native xmlns="http://cisco.com/ns/yang/ned/ios">
            ...     <version>
            ...     </version>
            ...     </native>
            ...     </filter>
            ...     </get>
            ...     </rpc>
            ...     """
            >>> reply = device.nc.request(netconf_request)
            >>>

        Expected Results::

            >>> print(reply)
            <?xml version="1.0" encoding="UTF-8"?>
            <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"
            message-id="101"><data>
            <native xmlns="http://cisco.com/ns/yang/ned/ios">
            <version>16.3</version></native></data></rpc-reply>
            >>>
        '''

        rpc = RawRPC(session = self.session,
                     device_handler = self._device_handler,
                     timeout = timeout,
                     raise_mode = operations.rpc.RaiseMode.NONE)

        # identify message-id
        m = re.search(r'message-id="([A-Za-z0-9_\-:# ]*)"', msg)
        if m:
            rpc._id = m.group(1)
            rpc._listener.register(rpc._id, rpc)
            logger.debug('Found message-id="%s" in your rpc, which is good.', rpc._id)
        else:
            logger.warning('Cannot find message-id in your rpc. You may '
                           'expect an exception when receiving rpc-reply '
                           'due to missing message-id.')

        return rpc._request(msg).xml

    def __getattr__(self, method):
        # avoid the __getattr__ from Manager class
        if method in manager.VENDOR_OPERATIONS or method in manager.OPERATIONS:
            return super().__getattr__(method)
        else:
            raise AttributeError("'%s' object has no attribute '%s'"
                                 % (self.__class__.__name__, method))

class RawRPC(operations.rpc.RPC):
    '''RawRPC

    A modified ncclient.operations.rpc.RPC class. This is for internal use
    only.
    '''

    def _request(self, msg):
        '''_request

        Override method _request in class ncclient.operations.RPC, so it can
        handle raw rpc requests in string format without validating your rpc
        request syntax. When your rpc-reply is received, in most cases, it
        simply returns rpc-reply again in string format, except one scenario:
        If message-id is missing or message-id received does not match that in
        rpc request, ncclient will raise an OperationError.
        '''

        logger.debug('Requesting %r' % self.__class__.__name__)
        logger.info('Sending rpc...')
        logger.info(msg)
        time1 = time.time()
        self._session.send(msg)
        if not self._async:
            logger.debug('Sync request, will wait for timeout=%r' %
                         self._timeout)
            self._event.wait(self._timeout)
            if self._event.isSet():
                time2 = time.time()
                reply_time = "{:.3f}".format(time2 - time1)
                logger.info('Receiving rpc-reply after {} sec...'.
                            format(reply_time))
                logger.info(self._reply)
                return self._reply
            else:
                logger.info('Timeout. No rpc-reply received.')
                raise TimeoutExpiredError('ncclient timed out while waiting '
                                          'for an rpc-reply.')
