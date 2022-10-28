import os
import logging
from threading import Thread, Event
from datetime import datetime
from collections import deque
from google.protobuf import json_format
import grpc
from . import proto

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
    def request(self, request=None):
        if request is None:
            request = {}
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
                        self.result = self.response_verify(
                            resp, self.returns.copy())
                else:
                    self.log.error('No values in subscribe response')

    def run(self):
        """Check for inbound notifications."""
        t1 = datetime.now()
        self.log.info('\nSubscribe notification active\n{0}'.format(29 * '='))
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
                    self.log.info('\nSubscribe response:\n{0}\n{1}'.format(
                        19 * '=', str(response)))
                    self.process_opfields(response)

        except Exception as exc:
            msg = ''
            if hasattr(exc, 'details'):
                msg += f'details: {exc.details()}'
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


class CiscoAuthPlugin(grpc.AuthMetadataPlugin):
    """A plugin which adds username/password metadata to each call."""

    def __init__(self, username, password):
        super(CiscoAuthPlugin, self).__init__()
        self.username = username
        self.password = password

    def __call__(self, context, callback):
        callback(
            [("username", self.username), ("password", self.password)],
            None
        )


class GnmiLogHandler(logging.Handler):

    @property
    def gnmi_session(self):
        return self._gnmi_session

    @gnmi_session.setter
    def gnmi_session(self, session):
        self._gnmi_session = session

    def emit(self, record):
        self.gnmi_session.results.append(record.msg)


class Gnmi(BaseConnection):
    """Session handling for gNMI connections.

    Can be used with pyATS same as yang.connector.Netconf is used or
    can be used as a standalone module.

    Methods:

    capabilities(): gNMI Capabilities.\n
    set(dict): gNMI Set. Input is namespace, xpath/value pairs.\n
    get(dict): gNMI Get mode='STATE'. Input xpath/value pairs (value optional).\n
    subscribe(dict): gNMI Subscribe. Input xpath/value pairs and format.\n

    pyATS Examples:

    >>> from pyats.topology import loader
    >>> from yang.connector.gnmi import Gnmi
    >>> testbed=loader.load('testbed.static.yaml')
    >>> device=testbed.devices['uut']
    >>> device.connect(alias='gnmi', via='yang2')
    >>> #####################
    >>> # Capabilities      #
    >>> #####################
    >>> resp=device.capabilities()
    >>> resp.gNMI_version
    '0.7.0'
    >>> #####################
    >>> # Get example       #
    >>> #####################
    >>> from yang.connector import proto
    >>> request = proto.gnmi_pb2.GetRequest()
    >>> request.type = proto.gnmi_pb2.GetRequest.DataType.Value('ALL')
    >>> request.encoding = proto.gnmi_pb2.Encoding.Value('JSON_IETF')
    >>> path = proto.gnmi_pb2.Path()
    >>> path1, path2, path3, path4 = (
            proto.gnmi_pb2.PathElem(),
            proto.gnmi_pb2.PathElem(),
            proto.gnmi_pb2.PathElem(),
            proto.gnmi_pb2.PathElem()
        )
    >>> path1.name, path2.name, path3.name, path4.name = (
            'syslog',
            'messages',
            'message',
            'node-name'
        )
    >>> path.elem.extend([path1, path2, path3, path4])
    >>> request.path.append(path)
    >>> resp = device.gnmi.get(request)
    >>> print(resp)
   """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.device = kwargs.get('device')
        dev_args = self.connection_info
        if dev_args.get('protocol', '') != 'gnmi':
            msg = 'Invalid protocol {0}'.format(dev_args.get('protocol', ''))
            raise TypeError(msg)

        self.active_notifications = {}
        root = None
        chain = None
        private_key = None
        self.channel = None
        self.results = deque()
        self.metadata = None
        username = dev_args.get('username', '')
        password = dev_args.get('password', '')

        if dev_args.get('custom_log', ''):
            self.log = dev_args.get('custom_log')
        else:
            self.log = log
            self.log.setLevel(logging.INFO)
            gnmi_log_handler = GnmiLogHandler()
            gnmi_log_handler.gnmi_session = self
            gnmi_log_handler.setLevel(logging.INFO)
            log.addHandler(gnmi_log_handler)
            self.log.addHandler(gnmi_log_handler)

        if not username or not password:
            creds = dev_args.get('credentials', '')
            if not creds:
                raise KeyError('No credentials found for testbed')
            if 'gnmi' not in creds:
                log.info('Credentials used from {0}'.format(next(iter(creds))))
            gnmi_uname_pwd = creds.get('')
            if not gnmi_uname_pwd:
                raise KeyError('No credentials found for gNMI')
            username = gnmi_uname_pwd.get('username', '')
            password = gnmi_uname_pwd.get('password', '')
            if not username or not password:
                raise KeyError('No credentials found for gNMI testbed')
        password = to_plaintext(password)

        port = str(dev_args.get('port'))
        target = '{0}:{1}'.format(
            dev_args.get('host'),
            port
        )
        options = [('grpc.max_receive_message_length', 1000000000)]
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
            override_name = dev_args.get('ssl_name_override', '')
            if override_name:
                self.log.info('Host override secure channel')
                options.append(
                    (
                        'grpc.ssl_target_name_override',
                        override_name
                    ),
                )
            self.log.info("Connecting secure channel")
            channel_ssl_creds = grpc.ssl_channel_credentials(
                root, private_key, chain
            )

            ssl_metadata = grpc.metadata_call_credentials(
                CiscoAuthPlugin(
                    username,
                    password
                )
            )
            channel_creds = grpc.composite_channel_credentials(
                channel_ssl_creds, ssl_metadata
            )
            self.channel = grpc.secure_channel(
                target, channel_creds, options
            )
        else:
            self.channel = grpc.insecure_channel(target)
            self.metadata = [
                ("username", username),
                ("password", password),
            ]
            self.log.info("Connecting insecure channel")

        self.service = proto.gnmi_pb2_grpc.gNMIStub(self.channel)

    @property
    def connected(self):
        """Return True if session is connected."""
        return self.service

    @property
    def gnmi(self):
        """Helper method to keep backwrads compatibility.

        Returns:
            Gnmi: self
        """
        return self

    def connect(self):
        """Connect to device using gNMI and get capabilities.

        Raises:
            gNMIException: No gNMI capabilities returned by device.
        """
        resp = self.capabilities()
        if resp:
            log.info('\ngNMI version: {0} supported encodings: {1}\n\n'.format(
                resp.gNMI_version,
                [proto.gnmi_pb2.Encoding.Name(i) for i in resp.supported_encodings]))
            log.info(banner('gNMI CONNECTED'))
        else:
            log.info(banner('gNMI Capabilities not returned'))
            self.disconnect()
            raise gNMIException('Connection not successful')

    def set(self, request):
        """Gnmi SET method.

        Args:
            request (proto.gnmi_pb2.SetRequest): gNMI SetRequest object

        Returns:
            proto.gnmi_pb2.SetResponse: gNMI SetResponse object
        """
        return self.service.Set(request, metadata=self.metadata)

    def configure(self, cmd):
        """Helper method for backwards compatibility.

        Args:
            cmd (proto.gnmi_pb2.SetRequest): gNMI SetRequest object

        Returns:
            proto.gnmi_pb2.SetResponse: gNMI SetResponse object
        """
        return self.set(cmd)

    def get(self, request):
        """Gnmi GET method.

        Args:
            request (proto.gnmi_pb2.GetRequest): gNMI GetResponse object

        Returns:
            proto.gnmi_pb2.GetResponse: gNMI GetResponse object
        """
        return self.service.Get(request, metadata=self.metadata)

    def execute(self, cmd):
        """Helper method for backwards compatibility.

        Args:
            cmd (proto.gnmi_pb2.GetRequest): gNMI GetResponse object

        Returns:
            proto.gnmi_pb2.GetResponse: gNMI GetResponse object
        """
        return self.get(cmd)

    def capabilities(self):
        """Gnmi Capabilities method.

        Returns:
            proto.gnmi_pb2.CapabilityResponse: gNMI Capabilities object
        """
        request = proto.gnmi_pb2.CapabilityRequest()
        return self.service.Capabilities(request, metadata=self.metadata)

    def subscribe(self, request_iter):
        """Gnmi Subscribe method.

        Args:
            request_iter (proto.gnmi_pb2.SubscribeRequest): gNMI SubscribeRequest object

        Returns:
            proto.gnmi_pb2.SubscribeResponse: gNMI SubscribeResponse object
        """
        return self.service.Subscribe(request_iter, metadata=self.metadata)

    def disconnect(self):
        """Disconnect from SSH device."""
        if self.connected:
            if self.channel:
                self.channel.close()
            del self.channel

    def __enter__(self):
        """Establish a session using a Context Manager."""
        if not self.connected:
            self.connect()
        return self

    def __exit__(self, *args):
        """Gracefully close connection on Context Manager exit."""
        self.disconnect()
