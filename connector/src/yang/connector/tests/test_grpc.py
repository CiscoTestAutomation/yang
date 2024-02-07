import os
import unittest
from unittest import mock
import subprocess

from unicon.plugins.tests.mock.mock_device_iosxe import MockDeviceTcpWrapperIOSXE
from unicon import Connection
from pyats.topology import loader
from time import sleep

telegraf_installed = subprocess.run(['which', 'telegraf']).returncode == 0


@unittest.skipIf(telegraf_installed is False, "Telegraf not installed on host")
class TestGrpc(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if subprocess.run(['which', 'telegraf']).returncode == 0:
            cls.telegraf_installed = True

    def setUp(self) -> None:
        self.md = MockDeviceTcpWrapperIOSXE(port=45678, state='enable', mock_data_dir='mock_devices',
                                            hostname='router-1')
        self.md.start()
        self.tb_yaml = f"""
devices:
  router-1:
    alias: router-1
    connections:
      a:
        ip: 127.0.0.1
        port: {self.md.ports[0]}
        protocol: telnet
      defaults:
        class: unicon.Unicon
      grpc:
        class: yang.connector.Grpc
        protocol: grpc
        transporter_ip: 127.0.0.1
        transporter_port: 56789
        autoconfigure: False
    credentials:
        default:
            username: user
            password: cisco123
    management:
      address:
        ipv4: 127.0.0.2
      interface: Ethernet0
    os: iosxe
    platform: isr4k
        """

    def tearDown(self) -> None:
        self.md.stop()
        os.remove('./transporter.conf')
        os.remove('./mdt.json')

    def test_connect_without_autoconfigure(self):
        tb_yaml = f"""
        devices:
          router-1:
            alias: router-1
            connections:
              a:
                ip: 127.0.0.1
                port: {self.md.ports[0]}
                protocol: telnet
              defaults:
                class: unicon.Unicon
              grpc:
                class: yang.connector.Grpc
                protocol: grpc
                transporter_ip: 127.0.0.1
                transporter_port: 56789
                autoconfigure: False
            credentials:
                default:
                    username: user
                    password: cisco123
            management:
              address:
                ipv4: 127.0.0.2
            os: iosxe
            platform: isr4k
                """
        testbed = loader.load(tb_yaml)

        dev = testbed.devices['router-1']
        dev.connect(via='grpc', alias='grpc')

        # give telegraf the opportunity to boot
        sleep(5)
        assert len(dev.connectionmgr.connections) == 1
        dev.grpc.disconnect()

    def test_connect_disconnect(self):
        testbed = loader.load(self.tb_yaml)
        dev = testbed.devices['router-1']
        dev.connect(via='grpc', alias='grpc')

        # give telegraf the opportunity to boot
        sleep(5)
        dev.grpc.disconnect()
  
    def test_connect_with_proxy_with_autoconfigure(self):
        tb_yaml = f"""
        devices:
          router-1:
            alias: router-1
            connections:
              a:
                ip: 127.0.0.1
                port: {self.md.ports[0]}
                protocol: telnet
              defaults:
                class: unicon.Unicon
              grpc:
                class: yang.connector.Grpc
                protocol: grpc
                transporter_ip: 127.0.0.1
                transporter_port: 56789
            credentials:
                default:
                    username: user
                    password: cisco123
            management:
              address:
                ipv4: 10.85.71.47/24
            os: iosxe
            platform: isr4k
                """
        testbed = loader.load(tb_yaml)
        proxy = Connection(hostname='linux',
                       start=['mock_device_cli --os linux --state connect_ssh'],
                       os='linux',
                       username='admin',
                       password='cisco')
        proxy.connectionmgr = mock.Mock()
        proxy.api = mock.Mock()
        dev = testbed.devices['router-1']
        dev.connections['grpc'].update({'sshtunnel':{'host':'proxy'}}) 
        testbed.devices['proxy'] = proxy
        with mock.patch('yang.connector.grpc.telegraf.sshtunnel.add_tunnel') as sshtunnel_mock:
          sshtunnel_mock.return_value = 123
          proxy.api.start_socat_relay.return_value = 321 , 123
          proxy.api.get_ip_route_for_ipv4.return_value = '127.0.0.0'
          dev.api = mock.Mock() 
          dev.connect(via='grpc', alias='grpc')
          proxy.api.start_socat_relay.assert_called_with('127.0.0.1', 123)
          dev.api.configure_telemetry_ietf_parameters.assert_called_with(sub_id=11172017, stream='yang-push', receiver_ip='127.0.0.0',
                                                                        receiver_port=321, protocol='grpc-tcp',source_vrf=None)

        # give telegraf the opportunity to boot
        sleep(5)
        dev.grpc.disconnect()
  
  
