import logging
import multiprocessing
import re
import socket
import configparser
import subprocess

try:
    from pyats.log.utils import banner
    from pyats.connections import BaseConnection
    from pyats.utils.secret_strings import to_plaintext
    from pyats.easypy import runtime
    from unicon import Connection
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

    class runtime:
        import os
        directory = os.curdir

    def banner(string):
        return string

    def to_plaintext(string):
        return string


# create a logger for this module
log = logging.getLogger(__name__)


class Grpc(BaseConnection):
    """Session handling for gNMI connections.

        Can be used with pyATS same as yang.connector.Netconf is used or
        can be used as a standalone module.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.device = kwargs.get('device')
        dev_args = self.connection_info
        self.log = log
        self.log.setLevel(logging.INFO)

        if protocol := dev_args.get('protocol', '').lower() != 'grpc':
            msg = f"Invalid protocol {protocol}"
            raise TypeError(msg)

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

        self.transporter = dev_args.get('transporter', 'telegraf').lower()
        self.output_file = dev_args.get('output_file', f'{runtime.directory}/mdt')
        self.config_file = dev_args.get('config_file', None)
        self.telegraf_pid = None

    @property
    def connected(self):
        """Return True if session is connected."""
        return True

    def connect(self):
        allocated_port = None

        def spawn_server_subprocess():
            # Allocate a random available port to localhost
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as grpc_socket:
                nonlocal allocated_port
                grpc_socket.bind(('localhost', 0))
                _, allocated_port = grpc_socket.getsockname()

                # run config generation within context manager to hold port until it can be passed to telegraf
                if self.transporter == 'telegraf':
                    config = configparser.ConfigParser()
                    if self.config_file:
                        # load configuration file
                        config.read(self.config_file)
                        if '[inputs.cisco_telemetry_mdt]' not in config.sections():
                            config.add_section('[inputs.cisco_telemetry_mdt]')

                        # update input socket listener
                        config.set('[inputs.cisco_telemetry_mdt]', 'transport', '"grpc"')
                        config.set('[inputs.cisco_telemetry_mdt]', 'service_address', f'":{allocated_port}"')

                        # write configuration file
                        with open(self.config_file, 'w') as f:
                            log.info(f"Writing config to {self.config_file}")
                            config.write(f)
                    else:
                        # set config file path
                        self.config_file = f"{runtime.directory}/telegraf.conf"
                        config.read(self.config_file)

                        # if the file already exists, only update the port
                        if config.sections():
                            if '[inputs.cisco_telemetry_mdt]' not in config.sections():
                                config.add_section('[inputs.cisco_telemetry_mdt]')

                            config.set('[inputs.cisco_telemetry_mdt]', 'transport', '"grpc"')
                            config.set('[inputs.cisco_telemetry_mdt]', 'service_address', f'":{allocated_port}"')

                            with open(self.config_file, 'w') as f:
                                log.info(f"Writing config to {self.config_file}")
                                config.write(f)
                        else:
                            # generate a default configuration file
                            with open(self.config_file, 'w') as f:
                                log.info(f"Creating telegraf config file {self.config_file}")
                                f.write('')

                            # create default config
                            # global tags
                            config.add_section('global_tags')
                            config.set('global_tags', 'user', r'"${USER}"')

                            # input configuration
                            config.add_section('[inputs.cisco_telemetry_mdt]')
                            config.set('[inputs.cisco_telemetry_mdt]', 'transport', '"grpc"')
                            config.set('[inputs.cisco_telemetry_mdt]', 'service_address', f'":{allocated_port}"')

                            # default output config - to file in runtime or user supplied dir
                            config.add_section('[outputs.file]')
                            config.set('[outputs.file]', 'files', f'["stdout", "{self.output_file}"]')
                            config.set('[outputs.file]', 'data_format', '"json"')
                            config.set('[outputs.file]', 'json_timestamp_units', '"1ms"')
                            config.set('[outputs.file]', 'rotation_max_size', '"2048MB"')
                            config.set('[outputs.file]', 'flush_jitter', '"500ms"')

                            # apply config
                            with open(self.config_file, 'w') as f:
                                log.info(f"Updating {self.config_file}")
                                config.write(f)

                # exit context manager to release port
                # spawn telegraf/pipeline using config
                subprocess.run(f"telegraf -config '{self.config_file}' &", shell=True)
                ps_out = subprocess.run(f"ps | grep telegraf | grep -v grep",
                                        shell=True, stdout=subprocess.PIPE, text=True)
                self.telegraf_pid = int(re.findall(r'^\d+', ps_out.stdout.strip())[0])

                # log port
                log.info(f"Server is listening on port {allocated_port}")
                log.info(f"Telegraf is running as PID {self.telegraf_pid}")

        grpc_inbound_server_process = multiprocessing.Process(target=spawn_server_subprocess())
        grpc_inbound_server_process.start()
        log.info(f"Starting gRPC inbound server on localhost:{allocated_port}")

        # call the API to genie configure the service on the device

    def disconnect(self):
        if self.telegraf_pid:
            subprocess.run(f"kill {self.telegraf_pid}", shell=True)
