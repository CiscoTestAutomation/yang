import logging
import socket
import configparser
import subprocess
import re

from pyats.easypy import runtime
from unicon.bases.connection import Connection
from unicon.sshutils import sshtunnel


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
        poll_status = self.transport_process.poll()
        if not poll_status:
            # when poll returns None then the process is still alive
            return True
        else:
            # when process is killed, poll returns its exit code
            return poll_status

    def connect(self):
        """
        Configures and starts a telegraf process on the machine that executes the connect method wherin
        telegraf is opened in a Python subprocess.

        The network device is then connected via Unicon CLI and the outbound telemetry process that corresponds
        to the booted telegraf process is configured on the device, with the CLI connection remaining open
        """

        # Allocate a random available port to localhost
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as grpc_socket:
            grpc_socket.bind(('0.0.0.0', 0))
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
                self.config_file = f"{self.config_directory}/transporter.conf"
                with open(f"{self.config_file}", 'w') as f:
                    log.info(f"Writing config to {self.config_file}")
                    config.write(f)
            else:
                # set config file path
                self.config_file = f"{runtime.directory}/transporter.conf"
                config.read(self.config_file)

                # if the file already exists, only update the port
                if config.sections():
                    if '[inputs.cisco_telemetry_mdt]' not in config.sections():
                        config.add_section('[inputs.cisco_telemetry_mdt]')

                    config.set('[inputs.cisco_telemetry_mdt]', 'transport', '"grpc"')
                    config.set('[inputs.cisco_telemetry_mdt]', 'service_address', f'":{allocated_port}"')

                    # Don't overwrite first file, stick that in /tmp/
                    self.config_file = f"{self.config_directory}/transporter.conf"
                    with open(f"{self.config_directory}/transporter.conf", 'w') as f:
                        log.info(f"Writing config to {self.config_directory}/transporter.conf")
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
        if subprocess.run(['which', 'telegraf']).returncode == 0:
            self.transport_process = subprocess.Popen(f"telegraf -config '{self.config_file}'", shell=True)
            # log port
            log.info(f"Telegraf is running as PID {self.transport_process.pid} on port {allocated_port}")
        else:
            raise OSError('Telegraf is not installed')
        breakpoint()
        proxy_ip = None
        if self.proxy:
            # connect to proxy 
            try:
                proxy_dev = self.device.testbed.devices[self.proxy]
            except:
                log.info('The proxy is not defined in the testbed devices. searching the servers')
                try:
                    proxy_dev = self.device.api.convert_server_to_linux_device(self.proxy)
                except Exception as e:
                    log.error(f'Could not convert server to device because of {e}')
                    raise e
            #connect to proxy
            proxy_dev.connect()
            # add a remote tunnel on the proxy for the allocated port on the execution host
            remote_tunnel_port = sshtunnel.add_tunnel(proxy_conn=proxy_dev.connectionmgr.connections.cli, tunnel_type='remote', target_port=allocated_port)
            # create a proxy port on the proxy using socat api for redirecting traffic to the port for remote tunnel 
            proxy_port = proxy_dev.api.socat_relay('127.0.0.1', remote_tunnel_port)
            mgmt_ip = self.access_ip or self.device.management.get('address').get('ipv4')
            if mgmt_ip:
                route_output = proxy_dev.execute(f'ip route get {mgmt_ip.ip}')
                pattern = re.compile(r'.*src (?P<route>[0-9.]+).*')
                route_match = pattern.match(route_output)
                if route_match:
                    proxy_ip = route_match.groupdict().get('route')
            else:
                raise('There is no ipv4 defined under management in the testbed ')
        if self.telemetry_autoconfigure:
            # check if there is an existing unicon connection
            active_connection = None
            for conn_alias in self.device.connectionmgr.connections:
                conn = self.device.connectionmgr.connections[conn_alias]
                if isinstance(conn, Connection) and conn.connected:
                    active_connection = conn_alias
                    break
            # create one if there isn't
            if not active_connection:
                self.device.instantiate()
                if 'unicon' in self.device.default.__module__:
                    self.device.connect()
                else:
                    raise ValueError('Connection Class is not Unicon')
                active_connection = self.device.connectionmgr.connections._default_alias

            # run configurations while ensuring that it is using a unicon default connection
            with self.device.temp_default_alias(active_connection):
                local_ip = self.transporter_ip or self.device.api.get_local_ip()
                # the ip for receiving data which will be configured on the device this could be the ip of 
                # the proxy connected to device or the ip of the execution host or transporter 
                receiver_ip = proxy_ip or local_ip
                self.device.api.configure_netconf_yang()
                if self.proxy:
                    self.device.api.configure_telemetry_ietf_parameters(sub_id=self.telemetry_subscription_id, stream="yang-push", receiver_ip=receiver_ip,
                                                                        receiver_port=proxy_port, protocol="grpc-tcp", source_vrf=self.vrf)
                else:
                    self.device.api.configure_telemetry_ietf_parameters(sub_id=self.telemetry_subscription_id,stream="yang-push",
                                                                        receiver_ip=receiver_ip, receiver_port=allocated_port, protocol="grpc-tcp", source_vrf=self.vrf)       

            self.device.connections['grpc'].update({
                'transporter_ip': receiver_ip,
                'transporter_port': allocated_port
            })
            if self.proxy:
                log.info('Using proxy for connecting to the transporter')
                log.info(f"Started gRPC inbound server on {local_ip}:{allocated_port} via {proxy_ip}:{proxy_port}")
            else:
                log.info(f"Started gRPC inbound server on {local_ip}:{allocated_port}")
        else:
            self.device.connections['grpc'].update({
                'transporter_ip': "0.0.0.0",
                'transporter_port': allocated_port
            })
            log.info(f"Started gRPC inbound server on 0.0.0.0:{allocated_port}")

    def disconnect(self):
        """
        Terminates the running telegraf process on the local machine, deconfigures the subscription from the device
        and disconnects from the subordinate CLI connection
        """
        self.transport_process.terminate()
        if self.telemetry_autoconfigure:
            self.device.api.unconfigure_telemetry_ietf_subscription(self.telemetry_subscription_id)
            self.device.disconnect()
