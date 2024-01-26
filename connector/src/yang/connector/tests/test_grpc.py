import os
import unittest
import subprocess
from unicon.plugins.tests.mock.mock_device_iosxe import MockDeviceTcpWrapperIOSXE
from unicon.mock.mock_device import MockDeviceSSHWrapper

from pyats.topology import loader
from time import sleep

telegraf_installed = subprocess.run(['which', 'telegraf']).returncode == 0


@unittest.skipIf(telegraf_installed is False, "Telegraf not installed on host")
class TestGrpc(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if subprocess.run(['which', 'telegraf']).returncode == 0:
            cls.telegraf_installed = True
        cls.tunnel_host_md = MockDeviceSSHWrapper(device_os='linux', port=0, state='exec')
        cls.tunnel_host_md.start()

    def setUp(self) -> None:
        # self.md = MockDeviceTcpWrapperIOSXE(port=0, state='enable', mock_data_dir='mock_devices',
        #                                     hostname='router-1')
        # self.md.start()
        # self.tunnel_host_md = MockDeviceSSHWrapper(device_os='linux', port=0, state='exec')
        # self.tunnel_host_md.start()

        self.tb_yaml = f"""
devices:
  proxy:
    os: linux
    type: server
    connections:
      defaults:
        class: unicon.Unicon
      ssh:
        protocol: ssh
        ip: 127.0.0.1
        port: {self.tunnel_host_md.ports[0]}
        ssh_options: -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null
        """

    def tearDown(self) -> None:
        self.md.stop()
        self.tunnel_host_md.stop()
        os.remove('./transporter.conf')
        os.remove('./mdt.json')

    def test_connect_without_autoconfigure(self):
        tb_yaml = f"""
        devices:
          proxy:
            os: linux
            type: server
            connections:
              defaults:
                class: unicon.Unicon
              ssh:
                protocol: ssh
                ip: 127.0.0.1
                port: {self.tunnel_host_md.ports[0]}
                ssh_options: -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null
                """
        testbed = loader.load(tb_yaml)
        breakpoint()
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
