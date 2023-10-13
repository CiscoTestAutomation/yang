import os
import unittest
from unicon import Connection
from unicon.plugins.tests.mock.mock_device_iosxe import MockDeviceTcpWrapperIOSXE

from yang.connector import grpc
from pyats.topology import loader
from pyats.datastructures import attrdict


class TestGrpc(unittest.TestCase):
    def setUp(self) -> None:
        self.md = MockDeviceTcpWrapperIOSXE(port=45678, state='enable', mock_data_dir='mock_devices', hostname='router-1')
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
        ip: 10.10.0.1
        protocol: grpc
        transporter_ip: 127.0.0.1
        transporter_port: 56789
    credentials:
        default:
            username: user
            password: cisco123
    os: iosxe
    platform: isr4k
        """

    def tearDown(self) -> None:
        self.md.stop()
        os.remove('./telegraf.conf')
        os.remove('./mdt')

    def test_connect_disconnect(self):
        testbed = loader.load(self.tb_yaml)
        dev = testbed.devices['router-1']
        dev.connect(via='grpc', alias='grpc')

        dev.grpc.disconnect()
