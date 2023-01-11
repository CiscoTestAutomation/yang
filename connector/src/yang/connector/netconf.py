"""netconf.py module is a wrapper around the ncclient package."""

import re
import time
import atexit
import logging
import subprocess
import datetime
import lxml.etree as et
from time import sleep
from threading import Thread, Event
from ncclient import manager
from ncclient import operations
from ncclient import transport
from ncclient.operations.retrieve import GetReply
from ncclient.devices.default import DefaultDeviceHandler
from ncclient.operations.errors import TimeoutExpiredError

try:
    from pyats.connections import BaseConnection
    from pyats.utils.secret_strings import to_plaintext
    from pyats.log.utils import banner
    from pyats.log import TaskLogFormatter
except ImportError:
    class BaseConnection:
        pass

from .settings import Settings


# create a logger for this module
logger = logging.getLogger(__name__)

nccl = logging.getLogger("ncclient")
# The 'Sending' messages are logged at level INFO.
# The 'Received' messages are logged at level DEBUG.

LOG_FORMAT = '%(asctime)s: %%NETCONF-%(levelname)s: %(message)s'
DATE_FORMAT = '%Y-%m-%dT%H:%M:%S'


def format_xml(msg):
    parser = et.XMLParser(recover=True, remove_blank_text=True)

    if isinstance(msg, str):
        msg = msg.encode("utf-8")

    msg = msg.strip()

    start = msg.find(b"<")
    end = msg.rfind(b"]]>]]>")   # NETCONF 1.0 terminator

    if end == -1:
        end = msg.rfind(b">")
        if end != -1:
            # Include the '>' character in our range
            end += 1

    if start != -1 and end != -1:
        try:
            elem = et.fromstring(msg[start:end], parser)
            text = et.tostring(elem, pretty_print=True,
                               encoding="utf-8")
            msg = (msg[:start] + text + msg[end:])
        except Exception as err:
            logger.exception(err)

    return msg.decode()

class NetconfFormatter(logging.Formatter):
    """
        For formatting NETCONF XML messages
    """
    def __init__(self, fmt=LOG_FORMAT, date_fmt=DATE_FORMAT):
        super().__init__(fmt=fmt,
                         datefmt=date_fmt)

        self.FORMAT_XML = True

    def format(self, record):
        msg = record.msg
        if isinstance(msg, operations.rpc.RPCReply):
            msg = msg.xml
        if self.FORMAT_XML:
            record.msg = format_xml(msg)
        return super().format(record)


class NetconfScreenFormatter(NetconfFormatter):
    """
        For limiting the output for formatted messages, max 40 lines by default
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.MAX_LINES = 40
        self.FORMAT_XML = True

    def format(self, record):
        msg = super().format(record)
        lines = msg.splitlines()
        if self.MAX_LINES:
            msg_len = len(lines)
            if msg_len > self.MAX_LINES:
                half_lines = int(self.MAX_LINES/2)
                return '\n'.join(lines[0:half_lines] + \
                                 [f'\n\n... skipping {msg_len-self.MAX_LINES} lines ...\n\n'] + \
                                 lines[-half_lines:])
            else:
                return '\n'.join(lines)
        else:
            return msg


class pyATS_TaskLog_Adapter(logging.StreamHandler):

    def __init__(self):
        logging.Handler.__init__(self)
        try:
            from pyats.log import managed_handlers
            self._pyats_handlers = managed_handlers
        except Exception:
            raise Exception('Cannot use pyATS log adapter when pyATS is not importable')

    @property
    def stream(self):
        return self._pyats_handlers.tasklog.stream


class NetconfSessionLogHandler(logging.Handler):
    """Logging handler that pretty prints ncclient XML."""

    parser = et.XMLParser(recover=True)

    def emit(self, record):
        if hasattr(record, 'session'):
            try:
                # If the message contains XML, pretty-print it
                record.args = list(record.args)

                for i in range(len(record.args)):
                    arg = None
                    if isinstance(record.args[i], str):
                        arg = record.args[i].encode("utf-8")
                    elif isinstance(record.args[i], bytes):
                        arg = record.args[i]
                    if not arg:
                        continue
                    record.args[i] = format_xml(arg)

                record.args = tuple(record.args)
            except Exception:
                # Unable to handle record so leave it unchanged
                pass


nccl.addHandler(NetconfSessionLogHandler())


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
        # set default timeout
        kwargs.setdefault('timeout', 30)

        self.alias = kwargs.get('alias')
        self.debug = kwargs.get('debug', False)
        self.logfile = kwargs.get('logfile')
        self.logdir = kwargs.get('logdir', '/tmp')
        self.log_propagate = kwargs.get('log_propagate', False)
        self.log_stdout = kwargs.get('log_stdout', True)
        self.no_pyats_tasklog = kwargs.get('no_pyats_tasklog', False)

        # instanciate BaseConnection
        # (could use super...)
        BaseConnection.__init__(self, *args, **kwargs)
        if 'timeout' in self.connection_info:
            self.timeout = self.connection_info['timeout']

        # connection_info is set by BaseConnection class
        self.settings = self.connection_info.pop('settings', Settings())

        # shortwire Ncclient device handling portion
        # and create just the DeviceHandler
        device_handler = DefaultDeviceHandler()

        # create the session instance
        session = transport.SSHSession(device_handler)

        # load known_hosts file (if available)
        if kwargs.get('hostkey_verify'):
            session.load_known_hosts()

        # instanciate ncclient Manager
        # (can't use super due to mro change)
        manager.Manager.__init__(
            self, session=session, device_handler=device_handler,
            timeout=self.timeout)

        self.active_notifications = {}

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

    def configure_logging(self):

        # use device name or connection id
        hostname = self.device.name if hasattr(self, 'device') else id(self)

        if self.alias:
            logger_name = '%s.%s.%s' % (hostname,
                                        self.alias,
                                        int(time.time()))
        else:
            logger_name = '%s.%s' % (hostname, int(time.time()))

        self.log = logging.getLogger('netconf.%s' % logger_name)

        # workaround for double invocation that somehow happens in robot
        self.log.handlers.clear()
        self.log.filters.clear()

        # default log level
        self.log.setLevel(logging.INFO)
        # don't... propagate
        self.log.propagate = self.log_propagate

        # add logfile
        if self.logfile is None:
            try:
                from pyats.easypy import runtime
                if runtime.job is not None:
                    self.logdir = runtime.directory
            except Exception:
                pass

            ts = datetime.datetime.now().strftime('%Y%m%dT%H%M%S.%f')[:-3].replace('.', '')
            def convert(string):
                return re.sub(r'[^\w\s-]', '_', string)
            sanitized_hostname = convert(hostname)
            if self.alias:
                self.logfile = f'{self.logdir}/{sanitized_hostname}-{self.alias}-{ts}.log'
            else:
                self.logfile = f'{self.logdir}/{sanitized_hostname}-{ts}.log'

        if self.log_stdout:
            hdlr = logging.StreamHandler()
            screen_formatter = NetconfScreenFormatter(fmt=LOG_FORMAT)
            screen_formatter.MAX_LINES = self.settings.get('NETCONF_SCREEN_LOGGING_MAX_LINES', 40)
            screen_formatter.FORMAT_XML = self.settings.get('NETCONF_LOGGING_FORMAT_XML', True)
            hdlr.setFormatter(screen_formatter)
            self.log.addHandler(hdlr)

        if self.logfile:
            fh = logging.FileHandler(self.logfile)
            file_formatter = NetconfFormatter(fmt=LOG_FORMAT)
            file_formatter.FORMAT_XML = self.settings.get('NETCONF_LOGGING_FORMAT_XML', True)
            fh.setFormatter(file_formatter)
            self.log.addHandler(fh)
            logger.info('+++ %s netconf logfile %s +++' % (hostname, self.logfile))

        # are we in pyATS?
        try:
            from pyats.log import managed_handlers  # noqa
        except Exception:
            # we're not, let go
            pass
        else:
            # we're in pyATS, use pyATS loggers
            if not self.no_pyats_tasklog:
                pta = pyATS_TaskLog_Adapter()
                nsf = NetconfScreenFormatter(fmt=TaskLogFormatter.MESSAGE_FORMAT)
                nsf.MAX_LINES = self.settings.get('NETCONF_SCREEN_LOGGING_MAX_LINES', 40)
                nsf.FORMAT_XML = self.settings.get('NETCONF_LOGGING_FORMAT_XML', True)
                pta.setFormatter(nsf)
                self.log.addHandler(pta)

        # if debug_mode is True, enable debug mode
        if self.debug:
            self.log.setLevel(logging.DEBUG)

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

        self.configure_logging()

        if not self.session.is_alive():
            self._session = transport.SSHSession(self._device_handler)

        # default values
        defaults = {
            'host': None,
            'port': 830,
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
                defaults['username'] = str(
                    self.connection_info['credentials']['netconf']['username'])
            except Exception:
                pass
            try:
                defaults['password'] = to_plaintext(
                    self.connection_info['credentials']['netconf']['password'])
            except Exception:
                pass

        # support sshtunnel
        if 'sshtunnel' in defaults:
            from unicon.sshutils import sshtunnel
            try:
                tunnel_port = sshtunnel.auto_tunnel_add(self.device, self.via)
                if tunnel_port:
                    defaults['host'] = self.device.connections[self.via] \
                                           .sshtunnel.tunnel_ip
                    defaults['port'] = tunnel_port
            except AttributeError as err:
                raise AttributeError("Cannot add ssh tunnel. \
                Connection %s may not have ip/host or port.\n%s"
                                     % (self.via, err))
            del defaults['sshtunnel']

        defaults = {k: getattr(self, k, v) for k, v in defaults.items()}

        try:
            self.session.connect(**defaults)
            self.log.info('NETCONF CONNECTED')
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

    def subscribe(self, request):
        """ Creates a notification listener and mark it as active """
        notifier = Notification(self, request=request)
        notifier.start()
        if request['format']['request_mode'] == 'ON_CHANGE':
            # Get ready for trigger event
            notifier.event_triggered = True
        self.active_notifications[self] = notifier

    def notify_wait(self, steps):
        """ Activate notification listener and check results """
        notifier = self.active_notifications.get(self)
        if notifier:
            if steps.result.code != 1:
                notifier.stop()
                del self.active_notifications[self]
                return
            notifier.event_triggered = True
            self.log.info(banner('NOTIFICATION EVENT TRIGGERED'))
            wait_for_sample = notifier.sample_interval - 1
            cntr = 1.0
            while cntr < float(notifier.stream_max):
                self.log.info('Listening for notifications from subscribe stream, {} seconds elapsed'.format(
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
                steps.failed(
                    '\n' + banner('STREAM TIMED OUT WITHOUT RESPONSE')
                )

            if self in self.active_notifications:
                del self.active_notifications[self]

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

        time1 = datetime.datetime.now()
        reply = super().execute(cls, *args, **kwargs)
        time2 = datetime.datetime.now()
        reply.elapsed = time2 - time1
        return reply

    def request(self, msg, timeout=30, return_obj=False):
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
        return_obj : `boolean`, optional
            Normally a string is returned as a reply. In other cases, we may
            want to return a RPCReply object, so we can access some attributes,
            e.g., reply.ok or reply.elapsed.

        Returns
        -------

        str or RPCReply
            The reply from the device in string. If something goes wrong, an
            exception will be raised. If return_obj=True, the reply is a
            RPCReply object.


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
            ...     <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
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

        rpc = RawRPC(session=self.session,
                     device_handler=self._device_handler,
                     timeout=timeout,
                     raise_mode=operations.rpc.RaiseMode.NONE,
                     log=self.log)

        # identify message-id
        m = re.search(r'message-id="([A-Za-z0-9_\-:# ]*)"', msg)
        if m:
            rpc._id = m.group(1)
            rpc._listener.register(rpc._id, rpc)
            self.log.debug(
                'Found message-id="%s" in your rpc, which is good.', rpc._id)
        else:
            self.log.warning('Cannot find message-id in your rpc. You may '
                           'expect an exception when receiving rpc-reply '
                           'due to missing message-id.')

        # disable info logging for ncclient
        nccl.setLevel(logging.WARNING)

        if return_obj:
            response = rpc._request(msg)
        else:
            response = rpc._request(msg).xml

        # enable info logging for ncclient
        nccl.setLevel(logging.INFO)

        return response

    def __getattr__(self, method):
        # avoid the __getattr__ from Manager class
        if hasattr(manager, 'VENDOR_OPERATIONS') and method \
                in manager.VENDOR_OPERATIONS or method in manager.OPERATIONS:
            return super().__getattr__(method)
        else:
            raise AttributeError("'%s' object has no attribute '%s'"
                                 % (self.__class__.__name__, method))


class NetconfEnxr():
    """Subclass using POSIX pipes to Communicate NETCONF messaging."""

    chunk = re.compile('(\n#+\\d+\n)')
    rpc_pipe_err = """
        <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
        <rpc-error>
            <error-type>transport</error-type>
            <error-tag>resource-denied</error-tag>
            <error-severity>error</error-severity>
            <error-message>No pipe data returned</error-message>
        </rpc-error>
        </rpc-reply>"""

    def __init__(self, *args, **kwargs):
        self.manager = None
        self.proc = None
        self.buf = None
        self.server_capabilities = None

    def get_rpc(self, elements):
        """Return string representation of lxml element with rpc."""
        rpc_element = et.Element(
            'rpc',
            attrib={'message-id': '101'},
            nsmap={None: "urn:ietf:params:xml:ns:netconf:base:1.0"}
        )
        rpc_element.append(elements)
        return et.tostring(rpc_element,
                           pretty_print=True).decode()

    def recv_data(self):
        """Retrieve data from process pipe."""
        if not self.proc:
            logger.info('Not connected.')
        else:
            buf = ''
            while True:
                # TODO: Could be better...1 byte at a time...
                # but, too much buffer and it deadlocks!!
                data = self.proc.stdout.read(1)

                if not data:
                    return GetReply(self.rpc_pipe_err)

                buf += data

                if buf.endswith('\n##'):
                    buf = buf[:-3]
                    break

            logger.info(buf)
            buf = buf[buf.find('<'):]
            reply = re.sub(self.chunk, '', buf)
            return GetReply(reply)

    def request(self, rpc):
        return self.send_cmd(rpc)

    def configure(self, msg):
        '''configure

        High-level api: configure is a common method of console, vty and ssh
        sessions, however it is not supported by this NetconfEnxr class. This is
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

        raise Exception('configure is not a supported method of this NetconfEnxr '
                        'class, since a more suitable method, edit_config, is '
                        'recommended. There are nine netconf operations '
                        'defined by RFC 6241, and edit-config is one of them. '
                        'Also users can build any netconf requst, including '
                        'invalid netconf requst as negative test cases, in '
                        'XML format and send it by method request.')

    def send_cmd(self, rpc):
        """Send a message to process pipe."""
        if not self.proc:
            logger.info('Not connected.')
        else:
            if et.iselement(rpc):
                if not rpc.tag.endswith('rpc'):
                    rpc = self.get_rpc(rpc)
                else:
                    rpc = et.tostring(rpc, pretty_print=True).decode()
            rpc_str = '\n#' + str(len(rpc)) + '\n' + rpc + '\n##\n'
            logger.info(rpc_str)
            self.proc.stdin.write(rpc_str)
            self.proc.stdin.flush()

            return self.recv_data()

    def edit_config(self, target=None, config=None, **kwargs):
        """Send edit-config."""
        target = target
        config = config
        target_element = et.Element('target')
        et.SubElement(target_element, target)
        edit_config_element = et.Element('edit-config')
        edit_config_element.append(target_element)
        edit_config_element.append(config)
        return self.send_cmd(self.get_rpc(edit_config_element))

    def get_config(self, source=None, filter=None, **kwargs):
        """Send get-config."""
        source = source
        filter = filter
        source_element = et.Element('source')
        et.SubElement(source_element, source)
        get_config_element = et.Element('get-config')
        get_config_element.append(source_element)
        get_config_element.append(filter)
        return self.send_cmd(self.get_rpc(get_config_element))

    def get(self, filter=None, **kwargs):
        filter_arg = filter
        get_element = et.Element('get')
        if isinstance(filter_arg, tuple):
            type, filter_content = filter_arg
            if type == "xpath":
                get_element.attrib["select"] = filter_content
            elif type == "subtree":
                filter_element = et.Element('filter')
                filter_element.append(filter_content)
                get_element.append(filter_element)
        else:
            get_element.append(filter_arg)
        return self.send_cmd(self.get_rpc(get_element))

    def commit(self, **kwargs):
        commit_element = et.Element('commit')
        return self.send_cmd(self.get_rpc(commit_element))

    def discard_changes(self, **kwargs):
        discard_element = et.Element('discard-changes')
        return self.send_cmd(self.get_rpc(discard_element))

    def lock(self, target=None, **kwargs):
        target = target
        store_element = et.Element(target)
        target_element = et.Element('target')
        target_element.append(store_element)
        lock_element = et.Element('lock')
        lock_element.append(target_element)
        return self.send_cmd(self.get_rpc(lock_element))

    def unlock(self, target=None, **kwargs):
        target = target
        store_element = et.Element(target)
        target_element = et.Element('target')
        target_element.append(store_element)
        unlock_element = et.Element('unlock')
        unlock_element.append(target_element)
        return self.send_cmd(self.get_rpc(unlock_element))

    def dispatch(self, rpc_command=None, **kwargs):
        rpc = rpc_command
        return self.send_cmd(rpc)

    @property
    def connected(self):
        """Check for active connection."""

        return self.server_capabilities is not None and self.proc.poll() \
            is None

    def connect(self, timeout=None):
        """Connect to ENXR pipe."""
        if self.connected:
            msg = 'Already connected'

        CMD = ['netconf_sshd_proxy', '-i', '0', '-o', '1', '-u', 'lab']
        BUFSIZE = 8192

        p = subprocess.Popen(CMD, bufsize=BUFSIZE,
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT,
                             universal_newlines=True)

        buf = ''
        try:
            while True:
                data = p.stdout.read(1)
                if not data:
                    logger.info('No data received for hello')
                    p.terminate()
                    return

                buf += data
                if buf.endswith(']]>]]>'):
                    buf = buf[buf.find('<'):-6]
                    logger.info('Hello received')
                    break

            p.stdin.write(
                '<?xml version="1.0" encoding="UTF-8"?><hello '
                'xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"><capabilities>'
                '<capability>urn:ietf:params:netconf:base:1.1</capability>'
                '</capabilities></hello>]]>]]>'
            )
            p.stdin.flush()
            self.proc = p
            self.buf = ''
            elements = et.fromstring(buf)
            self.server_capabilities = [e.text for e in elements.iter()
                                        if hasattr(e, 'text')]
            # TODO: Notification stream interferes with get-schema
            msg = "NETCONF CONNECTED PIPE"
        except:
            msg = 'Not connected, Something went wrong'
        return msg

    def disconnect(self):
        """Disconnect from ENXR pipe."""
        if self.connected:
            self.proc.terminate()
            logger.info("NETCONF DISCONNECT PIPE")


class RawRPC(operations.rpc.RPC):
    '''RawRPC

    A modified ncclient.operations.rpc.RPC class. This is for internal use
    only.
    '''

    def __init__(self, *args, **kwargs):
        self.log = kwargs.pop('log', logging.getLogger(__name__))
        super().__init__(*args, **kwargs)

    def _request(self, msg):
        '''_request

        Override method _request in class ncclient.operations.RPC, so it can
        handle raw rpc requests in string format without validating your rpc
        request syntax. When your rpc-reply is received, in most cases, it
        simply returns rpc-reply again in string format, except one scenario:
        If message-id is missing or message-id received does not match that in
        rpc request, ncclient will raise an OperationError.
        '''

        self.log.debug('Requesting %r' % self.__class__.__name__)
        self.log.info('Sending rpc...')
        self.log.info(msg)
        time1 = datetime.datetime.now()
        self._session.send(msg)
        if not self._async:
            self.log.debug('Sync request, will wait for timeout=%r' %
                         self._timeout)
            self._event.wait(self._timeout)
            if self._event.isSet():
                time2 = datetime.datetime.now()
                self._reply.elapsed = time2 - time1
                self.log.info('Receiving rpc-reply after {:.3f} sec...'.
                            format(self._reply.elapsed.total_seconds()))
                self.log.info(self._reply)
                return self._reply
            else:
                self.log.info('Timeout. No rpc-reply received.')
                raise TimeoutExpiredError('ncclient timed out while waiting '
                                          'for an rpc-reply.')


class Notification(Thread):
    """ Listens for notifications, decodes, and verifies if any exists """
    def __init__(self, device, **request):
        Thread.__init__(self)
        self.device = device
        self.log = logging.getLogger(__name__)
        self.log.setLevel(logging.DEBUG)
        self._stop_event = Event()
        self.request = request
        self._event_triggered = False
        self._stopped = False

    @property
    def event_triggered(self):
        return self._event_triggered

    @event_triggered.setter
    def event_triggered(self, event_triggered):
        self._event_triggered = event_triggered

    @property
    def request(self):
        return self._request

    @request.setter
    def request(self, request={}):
        """ Sets the request property and propagates request's properties to the class """
        request_data = request['request']
        self.returns = request_data.get('returns')
        self.response_verify = request_data.get('verifier')
        self.decode_response = request_data.get('decode')
        self.namespace = request_data.get('namespace')
        self.sub_mode = request_data['format'].get('sub_mode', 'SAMPLE')
        self.encoding = request_data['format'].get('encoding', 'PROTO')
        self.sample_interval = request_data['format'].get('sample_interval', 10)
        if self.sub_mode == 'ON_CHANGE':
            self.sample_interval = 0
        self.stream_max = request_data['format'].get('stream_max', 0)
        self.time_delta = 0
        self.result = None
        self._event_triggered = False
        self._request = request_data

    def run(self):
        """ Start taking notifications until subscribe stream times out."""
        t1 = datetime.datetime.now()
        t2 = datetime.datetime.now()
        td = t2 - t1
        # Wait until after first sample period if sampling
        wait_for_sample = self.sample_interval - 1

        try:
            while self.time_delta < self.stream_max:
                t2 = datetime.datetime.now()
                td = t2 - t1

                if self.stopped():
                    self.time_delta = self.stream_max
                    self.log.info("Terminating notification thread")
                    break
                if self.stream_max:
                    t2 = datetime.datetime.now()
                    td = t2 - t1
                    self.time_delta = td.seconds
                    if td.seconds > self.stream_max:
                        self.stop()
                        break

                notif = self.device.take_notification(timeout=1)

                if notif and wait_for_sample <= 0:
                    resp_elements = self.decode_response(
                        notif.notification_xml
                    )
                    if resp_elements and self.returns:
                        self.result = self.response_verify(
                            resp_elements, self.returns
                        )
                        self.stop()
                        break
                wait_for_sample -= 1
        except Exception as exc:
            self.result = str(exc)
            self.log.error(str(exc))

    def stop(self):
        self.log.info("Stopping notification stream")
        self._stop_event.set()

    def stopped(self):
        return self._stop_event.is_set()
