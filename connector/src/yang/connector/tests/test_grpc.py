import os
import unittest
import subprocess
from unicon.plugins.tests.mock.mock_device_iosxe import MockDeviceTcpWrapperIOSXE

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
    credentials:
        default:
            username: user
            password: cisco123
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

        dev.grpc.disconnect()
