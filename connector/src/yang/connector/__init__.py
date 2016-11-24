"""yang.connector module defines a set of classes that connect to Data Model
Interfaces (DMI), in particular, an implementation of Netconf client. Restconf
implementation is coming next."""

# metadata
__version__ = '1.0.0'
__author__ = 'Jonathan Yang <yuekyang@cisco.com>'
__contact__ = 'yang-python@cisco.com'
__copyright__ = 'Cisco Systems, Inc. Cisco Confidential'

import paramiko
import socket
import time
import re
import logging
from ats.connections import BaseConnection

# create a LOGGER for this module
LOGGER = logging.getLogger(__name__)


# with a device object
# device.connect(alias='nc', via='netconf')
class Netconf(BaseConnection):
    '''Netconf

    Implementation of NetConf connection to devices (NX-OS, IOS-XR or IOS-XE),
    based on pyATS BaseConnection, allowing script servers to connect to end
    routers or swithes via NetConf protocol.

    YAML Example::

        connections:
            netconf:
                class: yang.connector.Netconf
                protocol : netconf
                ip : "1.2.3.4"
                port: 830
                user: admin
                password: admin

    Code Example::

        >>> from ats.topology import loader
        >>> testbed = loader.load('/users/xxx/xxx/asr_20_22.yaml')
        >>> device = testbed.devices['asr22']
        >>> device.connect(alias='nc', via='netconf')
        >>> device.nc.connected
        True
        >>> netconf_request = """
        ...     <rpc message-id="101"
        ...      xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
        ...     <get>
        ...     <filter>
        ...     <native xmlns="urn:ios">
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
        message-id="101"><data><native xmlns="urn:ios"><version>16.2</version>
        </native></data></rpc-reply>
        >>> device.nc.disconnect()
        >>> device.nc.connected
        False
        >>>

    Attributes
    ----------
    bufsize : `int`
        When paramiko channel method sendall is called, maximum self.bufsize
        bytes are sent at a time. By default, 16384 bytes is set and it
        works well in most cases. After a successful connection, users can
        retrieve or modify this value from attribute self.bufsize.

    timeout : `int`
        Timeout value in seconds which is used by paramiko channel. By
        default this value is 10 seconds. After a successful connection,
        users can retrieve this value from attribute self.timeout.

    framing : `string`
        After connection, attribute self.framing will contain the highest
        version of Chunked Framing Mechanism. "1.0" means
        ``urn:ietf:params:netconf:base:1.0`` and "1.1" refers to
        ``urn:ietf:params:netconf:base:1.1``.

    capabilities : `string`
        After connection, attribute self.capabilities contains capabilities
        infomation received from the device, and it has a list of data models
        that the device supports.

    last_reply_time : `int`
        Attribute self.last_reply_time records time measurement from sending
        out the message to receiving a reply (in seconds), and it is set by
        method request().
    '''


    def __init__(self, *args, **kwargs):
        '''
        __init__ instantiates a single connection instance.

        Parameters
        ----------

        bufsize : `int`, optional
            An optional keyed argument to set buffer size value in bytes. When
            paramiko channel method sendall is called, maximum self.bufsize
            bytes are sent at a time. By default, 16384 bytes is set and it
            works well in most cases. After a successful connection, users can
            retrieve this value from attribute self.bufsize.
        timeout : `int`, optional
            An optional keyed argument to set timeout value in seconds. By
            default this value is 10 seconds. After a successful connection,
            users can retrieve this value from attribute self.timeout.
        '''

        # instanciate parent BaseConnection
        super().__init__(*args, **kwargs)

        # check attribute connection_info is ready from class BaseConnection
        if hasattr(self, 'connection_info'):
            for key in ['class', 'protocol', 'ip', 'port', 'user', 'password']:
                if key not in self.connection_info:
                    raise Exception('''%s not defined in the YAML file, e.g.:
                                    netconf:
                                        class: yang.connector.Netconf
                                        protocol : netconf
                                        ip : "1.2.3.4"
                                        port: 830
                                        user: admin
                                        password: admin''' % key)
            if self.connection_info['protocol'] != 'netconf':
                raise Exception('wrong protocol defined in the YAML file. '
                                'Should be "netconf" but got "%s"'
                                % self.connection_info['protocol'])
        else:
            raise Exception('attribute connection_info does not exist. '
                            'Something in BaseConnection is wrong')

        # let's initialize some variables
        if 'bufsize' in kwargs:
            self.bufsize = kwargs['bufsize']
        else:
            self.bufsize = 16384
        if 'timeout' in kwargs:
            self.timeout = kwargs['timeout']
        else:
            self.timeout = 10
        self.socket = None
        self.ssh = None
        self.channel = None
        self.framing = '1.0'
        self.capabilities = ''
        self.last_reply_time = 0.0
        self.name = self.device.name

    @BaseConnection.locked
    def connect(self):
        '''connect

        high-level api: opens the NetConf connection and exchanges
        capabilities. After connection, attribute self.framing will contain the
        highest version of Chunked Framing Mechanism (either
        urn:ietf:params:netconf:base:1.0 or 1.1), and self.capabilities
        contains capabilities infomation received from the device.

        Parameters
        ----------

        bufsize : `int`, optional
            An optional keyed argument to set buffer size value in bytes. When
            paramiko channel method sendall is called, maximum self.bufsize
            bytes are sent at a time. By default, 16384 bytes is set and it
            works well in most cases. After a successful connection, users can
            retrieve this value from attribute self.bufsize.
        timeout : `int`, optional
            An optional keyed argument to set timeout value in seconds. By
            default this value is 10 seconds. After a successful connection,
            users can retrieve this value from attribute self.timeout.

        Raises
        ------

        Exception
            If the YAML file does not have correct connections section, or
            establishing transport to ip:port is failed, ssh authentication is
            failed, or unknown NetConf framing mechanism version is received.

        Note
        ----

        There is no return from this method. If something goes wrong, an
        exception will be raised.


        Example::

            >>> from ats.topology import loader
            >>> testbed = loader.load('/users/xxx/xxx/asr_20_22.yaml')
            >>> device = testbed.devices['asr22']
            >>> device.connect(alias='nc', via='netconf')
            >>>

        Expected Results::

            >>> device.nc.connected
            True
            >>> device.nc.framing
            '1.1'
            >>> device.nc.capabilities
            '<?xml version="1.0" encoding="UTF-8"?><hello>...</hello>'
            >>>
        '''

        # check if already connected
        if self.connected:
            LOGGER.info('NetConf is already connected to %s' % self.name)
            return

        # setup ssh transport
        address_list = socket.getaddrinfo(
            str(self.connection_info['ip']),
            self.connection_info['port'],
            family=socket.AF_INET,
            type=socket.SOCK_STREAM)
        for address in address_list:
            family, addr_type, protocol, canon_name, sock_addr = address
            try:
                skt = socket.socket(family, addr_type, protocol)
            except socket.error:
                skt = None
                continue
            skt.settimeout(self.timeout)
            try:
                skt.connect(sock_addr)
            except socket.error:
                skt.close()
                skt = None
                continue
            break
        if skt is None:
            raise Exception('Failed to establish transport to %s:%s'
                            % (str(self.connection_info['ip']),
                               self.connection_info['port']))
        else:
            self.socket = skt
        self.ssh = paramiko.Transport(self.socket)

        # setup ssh channel
        try:
            self.ssh.connect(
                hostkey=None,
                username=self.connection_info['user'],
                password=self.connection_info['password'])
        except paramiko.AuthenticationException:
            raise Exception('Authentication failed when connecting to %s:%s'
                            % (str(self.connection_info['ip']),
                               self.connection_info['port']))

        self.channel = self.ssh.open_session()
        self.channel.invoke_subsystem('netconf')
        self.channel.settimeout(self.timeout)

        # send hello and parse capabilities
        hello = """
            <?xml version="1.0" encoding="utf-8"?>
            <hello xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
              <capabilities>
                <capability>urn:ietf:params:netconf:base:1.0</capability>
                <capability>urn:ietf:params:netconf:base:1.1</capability>
              </capabilities>
            </hello>
            """
        msg = self.request(hello)
        self.capabilities = msg
        if re.search('urn:ietf:params:netconf:base:1.1', msg):
            self.framing = '1.1'
        elif re.search('urn:ietf:params:netconf:base:1.0', msg):
            self.framing = '1.0'
        else:
            raise Exception('Unknown NetConf framing mechanism version: %s'
                            % self.capabilities)
        LOGGER.info('NetConf is connected to %s' % self.name)

    @BaseConnection.locked
    def disconnect(self):
        '''disconnect

        high-level api: closes the NetConf session.

        Note
        ----

        There is no parameter or return of this method.


        Example::

            >>> from ats.topology import loader
            >>> testbed = loader.load('/users/xxx/xxx/asr_20_22.yaml')
            >>> device = testbed.devices['asr22']
            >>> device.connect(alias='nc', via='netconf')
            >>> device.nc.connected
            True
            >>> device.nc.disconnect()
            >>>

        Expected Results::

            >>> device.nc.connected
            False
            >>> device.nc.framing
            '1.0'
            >>> device.nc.capabilities
            ''
            >>>


        '''

        if self.channel is not None:
            self.channel.close()
            self.channel = None
        if self.ssh is not None:
            self.ssh.close()
            self.ssh = None
        if self.socket is not None:
            self.socket.close()
            self.socket = None
        self.framing = '1.0'
        self.capabilities = ''

    @BaseConnection.locked
    def request(self, msg, timeout=10):
        '''request

        high-level api: sends message through NetConf session and returns with
        a reply. Exception will be thrown out either the reply is in wrong
        format or timout. Users can modify timeout value (in seconds) by
        setting variable self.timeout. Variable self.last_reply_time records
        time measurement from sending out the message to receiving a reply (in
        seconds). Timeout default value is 10 seconds but it can be temporarily
        changed by passing an optional argument timeout=<seconds>, i.e.,
        self.timeout will be changed back to original self.timeout value
        after this call is done. Users may want to make a large query that
        requires a larger timeout.

        Parameters
        ----------

        msg : `str`
            Any message need to be sent out in XML format. The message can be
            in wrong format if it is a negative test case.
        timeout : `int`, optional
            An optional keyed argument to set timeout value in seconds. This is
            a temporarily change. The self.timeout value will be set to
            original self.timeout when this call is done.

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


        Example::

            >>> from ats.topology import loader
            >>> testbed = loader.load('/users/xxx/xxx/asr_20_22.yaml')
            >>> device = testbed.devices['asr22']
            >>> device.connect(alias='nc', via='netconf')
            >>> netconf_request = """
            ...     <rpc message-id="101"
            ...      xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
            ...     <get>
            ...     <filter>
            ...     <native xmlns="urn:ios">
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
            message-id="101"><data><native xmlns="urn:ios">
            <version>16.2</version></native></data></rpc-reply>
            >>>
        '''

        # check if already connected
        if not self.connected:
            raise Exception('NetConf is not connected')

        # set timeout temporarily
        if timeout != 10:
            original_timeout = self.timeout
            self.timeout = timeout
            self.channel.settimeout(timeout)

        # send and receive
        time1 = time.time()
        self.send(msg)
        reply = self.receive()
        time2 = time.time()
        self.last_reply_time = "{:.3f}".format(time2 - time1)
        LOGGER.info('Got NetConf reply from %s in %s sec' %
                    (self.name, self.last_reply_time))

        # set timeout back
        if timeout != 10:
            self.timeout = original_timeout
            self.channel.settimeout(original_timeout)

        return reply

    @property
    def connected(self):
        '''connected

        high-level api: checks whether NetConf connection is connected.

        Returns
        -------

        bool
            True or False that indicates whether the channel exists.


        Example::

            >>> from ats.topology import loader
            >>> testbed = loader.load('/users/xxx/xxx/asr_20_22.yaml')
            >>> device = testbed.devices['asr22']
            >>> device.connect(alias='nc', via='netconf')
            >>> device.nc.connected
            True
            >>>
        '''

        if self.channel is None:
            return False
        else:
            return True

    @BaseConnection.locked
    def configure(self, msg):
        '''configure

        high-level api: configure is a common method of console, vty and ssh
        sessions, however it is not supported by this Netconf class. This is
        just a placeholder in case someone mistakenly calls config method in a
        netconf session. An Exception will be thrown out with explanation.

        Parameters
        ----------

        msg : `str`
            Any config CLI need to be sent out.

        Raises
        ------

        Exception
            config is not a supported method of this Netconf class.
        '''

        raise Exception('configure is not a supported method of this Netconf '
                        'class, since a more flexible method, request, is '
                        'recommanded. There are nine netconf operations '
                        'defined by RFC 6241, and edit-config is only one of '
                        'them. Users can build any netconf requst, including '
                        'invalid netconf requst as negative test cases, in '
                        'XML format and send it by method request.')

    @BaseConnection.locked
    def execute(self, msg):
        '''execute

        high-level api: execute is a common method of console, vty and ssh
        sessions, however it is not supported by this Netconf class. This is
        just a placeholder in case someone mistakenly calls execute method in a
        netconf session. An Exception will be thrown out with explanation.

        Parameters
        ----------

        msg : `str`
            Any exec commands need to be sent out.

        Raises
        ------

        Exception
            execute is not a supported method of this Netconf class.
        '''

        raise Exception('execute is not a supported method of this Netconf '
                        'class, since a more flexible method, request, is '
                        'recommanded. There are nine netconf operations '
                        'defined by RFC 6241. get and get-config are only two '
                        'of them. Users can build any netconf requst, '
                        'including invalid netconf requst as negative test '
                        'cases, in XML format and send it by method request.')

    @BaseConnection.locked
    def send(self, msg):
        '''send

        public low-level api: sends request through NetConf session.

        Parameters
        ----------

        msg : `str`
            Any message need to be sent out in XML format. The message can be
            in wrong format if it is a negative test case.

        Raises
        ------

        Exception
            If NetConf is not connected, or an unknown NetConf framing
            mechanism version is set in the object.

        Note
        ----

        There is no return from this method. If something goes wrong, an
        exception will be raised.
        '''

        # check if already connected
        if not self.connected:
            raise Exception('NetConf is not connected')

        if self.framing == '1.0':
            self._send(msg + ']]>]]>')
        elif self.framing == '1.1':
            self._send('\n#%d\n' % len(msg) + msg + '\n##\n')
        else:
            raise Exception('Unknown NetConf framing mechanism version %s'
                            % self.framing)

    @BaseConnection.locked
    def receive(self):
        '''receive

        public low-level api: receives message from the NetConf session until
        all data are read. Exception will be thrown out either the reply is in
        wrong format or timout. Users can modify timeout value (in seconds) by
        setting variable self.timeout.

        Returns
        -------

        str
            The reply from the device in string.

        Raises
        ------

        Exception
            If NetConf is not connected, or there is a timeout when receiving
            reply.
        '''

        # check if already connected
        if not self.connected:
            raise Exception('NetConf is not connected')

        # try to receive from the NetConf session
        timeout = time.time() + self.timeout
        str_buffer = ''
        while time.time() < timeout:
            if self.channel.recv_ready():
                str_buffer += self._receive()
                str_ret = self._validate(str_buffer)
                if str_ret is not None:
                    return str_ret
            time.sleep(0.1)
        raise Exception('Timeout when receiving message from the NetConf '
                        'session. This is what we have received so far: "%s"'
                        % str_buffer)

    @BaseConnection.locked
    def _send(self, msg):
        '''_send

        low-level api: sends message through NetConf session. Exception will be
        thrown out if there is socket issues.

        Parameters
        ----------

        msg : `str`
            Any message need to be sent out through the channel.

        Raises
        ------

        Exception
            If NetConf is not connected, or there is a socket error when
            sending the message.

        Note
        ----

        There is no return from this method. If something goes wrong, an
        exception will be raised.
        '''

        # check if already connected
        if not self.connected:
            raise Exception('NetConf is not connected')

        try:
            # send message in batchs. The size of one batch is defined in
            # self.bufsize.
            if len(msg) < self.bufsize:
                self.channel.sendall(msg)
            else:
                while msg:
                    self.channel.sendall(msg[:self.bufsize])
                    msg = msg[self.bufsize:]
        except socket.error:
            raise Exception('Socket error when sending message to %s:%s'
                            % (str(self.connection_info['ip']),
                               self.connection_info['port']))

    @BaseConnection.locked
    def _receive(self):
        '''_receive

        low-level api: receives message from the NetConf session until all data
        are read. Exception socket.timeout could be raised if no data is ready.

        Returns
        -------

        str
            The reply from the device in string. This reply is a direct decode
            from data received on channel.

        Raises
        ------

        Exception
            If NetConf is not connected, or there is a timeout when receiving
            reply.
        '''

        # check if already connected
        if not self.connected:
            raise Exception('NetConf is not connected')

        str_buffer = ''
        while self.channel.recv_ready():
            str_buffer += self.channel.recv(self.bufsize).decode('utf-8')
        return str_buffer

    @BaseConnection.locked
    def _validate(self, msg):
        '''_validate

        low-level api: validates receiving message against RFC 6242. The method
        returns None if input message is invalid. Otherwise, non-None is
        returned, which is a string.

        Parameters
        ----------

        msg : `str`
            A message received from the channel, which is required to be
            verified against RFC 6242.

        Returns
        -------

        str or None
            None if the message is invalid. Otherwise, the message is returned
            with the version-specific framing removed.

        '''

        msg_len = len(msg)
        str_buffer = ''
        if self.framing == '1.0':
            if msg_len > 6 and msg[msg_len - 6:] == ']]>]]>':
                str_buffer = msg[:msg_len - 6]
                return str_buffer
            else:
                return None
        elif self.framing == '1.1':
            while msg_len > 0:
                if msg_len > 8:
                    ret = re.search('^\n#([0-9]+)\n', msg)
                    if ret is None:
                        return None
                    else:
                        msg_end = ret.end() + int(ret.group(1))
                        if msg_len >= msg_end + 4:
                            str_buffer += msg[ret.end():msg_end]
                            msg = msg[msg_end:]
                            msg_len = len(msg)
                            if msg[:4] == '\n##\n':
                                msg = msg[4:]
                                msg_len = len(msg)
                        else:
                            return None
                else:
                    return None
            return str_buffer
        else:
            raise Exception('Unknown NetConf framing mechanism version %s'
                            % self.framing)
