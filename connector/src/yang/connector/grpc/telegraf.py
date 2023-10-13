import logging
import socket
import configparser
import subprocess
import tempfile

from pyats.connections import BaseConnection
from pyats.easypy import runtime
from pyats.utils.secret_strings import to_plaintext
from unicon import Connection

from . import Grpc

# create a logger for this module
log = logging.getLogger(__name__)


class Grpc(Grpc):
    """
    Subclass for using Telegraf to collect telemetry
    """
    @property
    def connected(self):
        """Return True if session is connected."""
        return True

    def connect(self):
        # Allocate a random available port to localhost
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as grpc_socket:
            grpc_socket.bind(('localhost', 0))
            _, allocated_port = grpc_socket.getsockname()

            allocated_port = self.transporter_port or allocated_port

            # run config generation within context manager to hold port until it can be passed to telegraf
            config = configparser.ConfigParser()
            if self.config_file:
                # load configuration file
                config.read(self.config_file)
                if '[inputs.cisco_telemetry_mdt]' not in config.sections():
                    config.add_section('[inputs.cisco_telemetry_mdt]')

                # update input socket listener
                config.set('[inputs.cisco_telemetry_mdt]', 'transport', '"grpc"')
                config.set('[inputs.cisco_telemetry_mdt]', 'service_address', f'":{allocated_port}"')

                # write configuration file to temp dir and use that
                self.config_file = f"{self.config_directory}/telegraf.conf"
                with open(f"{self.config_file}", 'w') as f:
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

                    # Don't overwrite first file, stick that in /tmp/
                    self.config_file = f"{self.config_directory}/telegraf.conf"
                    with open(f"{self.config_directory}/telegraf.conf", 'w') as f:
                        log.info(f"Writing config to {self.config_directory}/telegraf.conf")
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
        self.transport_process = subprocess.Popen(f"telegraf -config '{self.config_file}'", shell=True)

        # log port
        log.info(f"Telegraf is running as PID {self.transport_process.pid} on port {allocated_port}")

        # call the API to genie configure the service on the device
        self.device.instantiate()
        if 'unicon' in self.device.default.__module__:
            self.device.connect()
        else:
            raise ValueError('Connection Class is not Unicon')
        local_ip = self.transporter_ip or self.device.api.get_local_ip()
        self.device.api.configure_netconf_yang()
        self.device.api.configure_telemetry_ietf_parameters(self.telemetry_subscription_id,
                                                            "yang-push", local_ip, allocated_port, "grpc-tcp")
        log.info(f"Started gRPC inbound server on {local_ip}:{allocated_port}")

    def disconnect(self):
        self.transport_process.terminate()
        self.device.api.unconfigure_telemetry_ietf_subscription(self.telemetry_subscription_id)
        self.device.disconnect()
