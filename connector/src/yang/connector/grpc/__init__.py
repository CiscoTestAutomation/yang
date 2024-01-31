import logging
import tempfile
import ipaddress
from importlib import import_module
from shutil import copyfile

try:
    from pyats.connections import BaseConnection
    from pyats.easypy import runtime
except ImportError:
    class BaseConnection:
        pass
    class runtime:
        pass

# create a logger for this module
log = logging.getLogger(__name__)


class Grpc(BaseConnection):
    """Session handling for Grpc outbound connections.

        Can be used with pyATS same as yang.connector

        EXAMPLE TESTBED

        devices:
          router-1:
            connections:
              a:
                ip: 10.10.0.1
                port: 23
                protocol: telnet
              grpc:
                protocol: grpc
                class: yang.connector.Grpc
                overwrite_config_file: True                                     (Optional, default: False)
                config_file: /Users/user/telemetry/router_1/config.conf         (Optional, default: ./transporter.conf)
                output_file: /Users/user/telemetry/router_1/output.txt          (Optional, default: ./mdt.json)
                telemetry_subscription_id: 501                                  (Optional, default: 11172017)
                transporter: telegraf                                           (Optional, default: telegraf)
                transporter_ip: 192.168.0.253                                   (Optional, default will fetch local IP)
                transporter_port: 56789                                         (Optional, default is a dynamic port)
                autoconfigure: True                                             (Optional, default: True)
            credentials:
              default:
                username: user
                password: cisco123
            os: iosxe

        EXAMPLE USAGE

        Welcome to pyATS Interactive Shell
        ==================================
        Python 3.11.5 (main, Sep 25 2023, 16:57:00) [Clang 14.0.0 (clang-1400.0.29.202)]

        >>> from pyats.topology.loader import load
        >>> testbed = load('/Users/user/testbed.yaml')
        -------------------------------------------------------------------------------
        >>> dev = testbed.devices['router-1.yaml']
        >>> dev.connect(via='grpc', alias='grpc')

    """
    def __new__(cls, *args, **kwargs):
        if '.'.join([cls.__module__, cls.__name__]) == \
                'yang.connector.grpc.Grpc':
            transporter = kwargs.get('transporter', 'telegraf')
            mod = import_module(f'yang.connector.grpc.{transporter}')
            new_cls = mod.Grpc
            return super().__new__(new_cls)
        return super().__new__(cls)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.device = kwargs.get('device')
        dev_args = self.connection_info
        self.log = log
        self.log.setLevel(logging.INFO)
        self.proxy = dev_args.get('sshtunnel', {}).get('host')
        self.source_address = kwargs.get('source_address')
        protocol = dev_args.get('protocol', 'grpc').lower()
        if protocol != 'grpc':
            msg = f"Invalid protocol {protocol}"
            raise TypeError(msg)
        if 'source_vrf' in kwargs:
            self.vrf = kwargs.get('source_vrf')
        else:
            self.vrf = self.device.management.get('vrf')  

        self.username = dev_args.get('username', '')
        self.password = dev_args.get('password', '')
        if not self.username or not self.password:
            credentials = dev_args.get('credentials', '')
            if not credentials:
                raise KeyError("No credentials found for testbed")
            if 'grpc' not in credentials:
                log.info(f"Credentials used from {next(iter(credentials))}")
            grpc_uname_pwd = credentials.get('')
            if not grpc_uname_pwd:
                raise KeyError('No credentials found for gRPC testbed')

        self.host = dev_args.get('host') or dev_args.get('ip')

        self.overwrite = dev_args.get('overwrite_config_file', False)
        if self.overwrite:
            self.config_directory = runtime.directory
        else:
            self.config_directory = tempfile.mkdtemp()
        self.output_file = dev_args.get('output_file', f"{runtime.directory}/mdt.json")
        try:
            self.config_file = copyfile(dev_args.get('config_file', None), f"{runtime.directory}/transporter.conf")
        except TypeError:
            self.config_file = None
        self.telemetry_subscription_id = dev_args.get('telemetry_subscription_id', 11172017)

        self.transport_process = None
        self.telemetry_autoconfigure = dev_args.get('autoconfigure', True)
        self.transporter_ip = dev_args.get('transporter_ip', None)
        self.transporter_port = dev_args.get('transporter_port', None)
