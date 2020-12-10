#!/bin/env python
""" Unit tests for the yang.connector cisco-shared package. """

import unittest
from ncclient import manager
from ncclient import transport
from ncclient.devices.default import DefaultDeviceHandler
from pyats.topology import loader
from pyats.connections import BaseConnection
from unittest.mock import Mock, patch
import yang.connector


class MyTransportSession():

    def __init__(self):
        pass

    def close(self):
        pass


class MySSHSession():

    def __init__(self):
        self._is_stopped = False
        self._connected = False
        self.transport = None

    @property
    def connected(self):
        return self._connected

    def connect(self, **kwargs):
        self._connected = True
        self.transport = MyTransportSession()

    def close(self):
        self._connected = False

    def send(self, message):
        pass

    def get_listener_instance(self, cls):
        pass

    def add_listener(self, listener):
        pass

    def is_alive(self):
        return True

class MySSHSession2():

    def __init__(self):
        self._is_stopped = False
        self._connected = False
        self.transport = None

    @property
    def connected(self):
        return self._connected

    def connect(self, **kwargs):
        if kwargs['username'] == 'admin' and kwargs['password'] == 'admin':
            self._connected = True
            self.transport = MyTransportSession()

    def close(self):
        self._connected = False

    def send(self, message):
        pass

    def get_listener_instance(self, cls):
        pass

    def add_listener(self, listener):
        pass

    def is_alive(self):
        return True

class MyRawRPC():

    def __init__(self, session=None, device_handler=None,
                       timeout=None, raise_mode=None):
        self._event = MyEvent()
        self._listener = MyRPCReplyListener()

    def _request(self, msg):
        return MyRPCReply()

class MyRPCReplyListener():

    def __init__(self):
        pass

    def register(self, id, rpc):
        pass

class MyRPCReply():

    def __init__(self):
        self.xml = '''
            <rpc-reply message-id="101"
             xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" >
            <data>
            <native xmlns="http://cisco.com/ns/yang/ned/ios">
            <version>16.3</version>
            </native>
            </data>
            </rpc-reply>
            '''

class MyCloseSession():

    def __init__(self, session, **kwargs):
        pass

    def request(self):
        return MyRPCReply()

class MyEvent():

    def __init__(self):
        pass

    def isSet(self):
        return True

    def wait(self, timeout):
        pass

class TestYang(unittest.TestCase):

    def setUp(self):
        self.yaml = \
            'devices:\n' \
            '    dummy:\n' \
            '        type: dummy_device\n' \
            '        connections:\n' \
            '            netconf:\n' \
            '                class: yang.connector.Netconf\n' \
            '                ip : "1.2.3.4"\n' \
            '                port: 830\n' \
            '                username: admin\n' \
            '                password: admin\n'

        self.testbed = loader.load(self.yaml)
        self.device = self.testbed.devices['dummy']
        self.nc_device = yang.connector.Netconf(device=self.device,
                                                alias='nc', via='netconf')

    def test_disconnect(self):
        self.nc_device._session = MySSHSession()
        self.nc_device.disconnect()
        generated_value = self.nc_device.connected
        expected_value = False
        self.assertEqual(generated_value, expected_value)

    def test_connect_1(self):
        self.nc_device._session = MySSHSession()
        self.nc_device.connect()
        generated_value = self.nc_device.connected
        expected_value = True
        self.assertEqual(generated_value, expected_value)

    def test_connect_2(self):
        self.nc_device._session = MySSHSession()
        self.nc_device.connect()
        generated_value = self.nc_device.connected
        expected_value = True
        self.assertEqual(generated_value, expected_value)

    def test_connect_3(self):
        nc_device = yang.connector.Netconf(device=self.device,
                                           alias='nc2',
                                           via='netconf',
                                           username='admin',
                                           password='admin')
        nc_device._session = MySSHSession2()
        nc_device.connect()
        generated_value = nc_device.connected
        expected_value = True
        self.assertEqual(generated_value, expected_value)

    def test_connect_4(self):
        nc_device = yang.connector.Netconf(device=self.device,
                                           alias='nc2',
                                           via='netconf',
                                           username='admi',
                                           password='admin')
        nc_device._session = MySSHSession2()
        nc_device.connect()
        generated_value = nc_device.connected
        expected_value = False
        self.assertEqual(generated_value, expected_value)

    @patch('yang.connector.netconf.RawRPC', new=MyRawRPC)
    def test_request(self):
        self.nc_device._session = MySSHSession()
        self.nc_device.connect()
        r = '''
             <rpc message-id="101"
              xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
             <get>
             <filter>
             <native xmlns="http://cisco.com/ns/yang/ned/ios">
             <version>
             </version>
             </native>
             </filter>
             </get>
             </rpc>
            '''
        generated_value = self.nc_device.request(r)
        expected_value = '''
            <rpc-reply message-id="101"
             xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" >
            <data>
            <native xmlns="http://cisco.com/ns/yang/ned/ios">
            <version>16.3</version>
            </native>
            </data>
            </rpc-reply>
            '''
        self.assertEqual(generated_value, expected_value)

    def test_rawrpc(self):
        from ncclient.operations.retrieve import GetReply

        h = DefaultDeviceHandler()
        self.rawrpc = yang.connector.netconf.RawRPC(session = transport.SSHSession(h),
                                            device_handler = h)
        self.rawrpc._event = MyEvent()
        self.rawrpc._session = MySSHSession()
        reply_raw = '''
            <rpc-reply message-id="101"
             xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" >
            <data>
            <native xmlns="http://cisco.com/ns/yang/ned/ios">
            <version>16.3</version>
            </native>
            </data>
            </rpc-reply>
            '''
        self.rawrpc._reply = GetReply(reply_raw)
        r = '''
             <rpc message-id="101"
              xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
             <get>
             <filter>
             <native xmlns="http://cisco.com/ns/yang/ned/ios">
             <version>
             </version>
             </native>
             </filter>
             </get>
             </rpc>
            '''
        generated_value = self.rawrpc._request(r).xml
        expected_value = '''
            <rpc-reply message-id="101"
             xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" >
            <data>
            <native xmlns="http://cisco.com/ns/yang/ned/ios">
            <version>16.3</version>
            </native>
            </data>
            </rpc-reply>
            '''
        self.assertEqual(generated_value, expected_value)

    def test_config(self):
        self.assertRaises(Exception,
                          self.nc_device.configure,
                          'logging console')

    def test_execute_1(self):
        manager.OPERATIONS = {
            "close_session": MyCloseSession,
        }
        self.nc_device.execute('close_session')
        generated_value = self.nc_device.connected
        expected_value = False
        self.assertEqual(generated_value, expected_value)

    def test_execute_2(self):
        self.assertRaises(Exception,
                          self.nc_device.execute,
                          'close')


if __name__ == '__main__':
    unittest.main()
