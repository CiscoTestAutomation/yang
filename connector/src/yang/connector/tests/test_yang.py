#!/bin/env python
""" Unit tests for the yang.connector cisco-shared package. """

import logging
import os
import tempfile
import unittest
from ncclient import manager
from ncclient import transport
from ncclient.devices.default import DefaultDeviceHandler
from pyats.topology import loader
from pyats.connections import BaseConnection
from pyats.datastructures import AttrDict
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
        self.connect_kwargs = kwargs
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
        self.connect_kwargs = kwargs
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
                       timeout=None, raise_mode=None, **kwarg):
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

    def test_connect_sshtunnel_logging(self):
        yaml = \
            'devices:\n' \
            '    dummy:\n' \
            '        os: iosxe\n' \
            '        type: dummy_device\n' \
            '        connections:\n' \
            '            netconf:\n' \
            '                class: yang.connector.Netconf\n' \
            '                protocol: netconf\n' \
            '                ip : "1.2.3.4"\n' \
            '                port: 830\n' \
            '                username: admin\n' \
            '                password: admin\n' \
            '                sshtunnel:\n' \
            '                    host: proxy\n'

        testbed = loader.load(yaml)
        device = testbed.devices['dummy']
        device.connections.netconf.sshtunnel = AttrDict(
            device.connections.netconf.sshtunnel)
        device.connections.netconf.sshtunnel.tunnel_ip = '127.0.0.1'
        logfile = tempfile.mktemp(suffix='.log')

        nc_device = yang.connector.Netconf(device=device,
                                           alias='nc',
                                           via='netconf',
                                           logfile=logfile,
                                           log_stdout=False,
                                           no_pyats_tasklog=True)
        nc_device._session = MySSHSession()

        def add_tunnel(device, via):
            logging.getLogger('unicon.sshutils').info(
                "Device '%s' connection '%s' via new SSH tunnel %s:%s",
                device.name, via, '127.0.0.1', 123)
            return 123

        try:
            with patch('unicon.sshutils.sshtunnel.auto_tunnel_add',
                       side_effect=add_tunnel):
                nc_device.connect()

            with open(logfile) as log_file:
                log_content = log_file.read()

            self.assertIn('via new SSH tunnel', log_content)
            self.assertIn('NETCONF CONNECTED', log_content)
            self.assertEqual(nc_device.session.connect_kwargs['host'],
                             '127.0.0.1')
            self.assertEqual(nc_device.session.connect_kwargs['port'], 123)
        finally:
            if os.path.exists(logfile):
                os.remove(logfile)

    def test_ncclient_session_logging(self):
        logfile = tempfile.mktemp(suffix='.log')
        nc_device = yang.connector.Netconf(device=self.device,
                                           alias='nc',
                                           via='netconf',
                                           logfile=logfile,
                                           log_stdout=False,
                                           no_pyats_tasklog=True)
        nc_device._session = MySSHSession()

        try:
            nc_device.connect()
            logging.getLogger('ncclient.transport.ssh').info(
                'Sending:\n%s', b'<hello/>',
                extra={'session': nc_device.session})

            with open(logfile) as log_file:
                log_content = log_file.read()

            self.assertIn('Sending:', log_content)
            self.assertIn('<hello/>', log_content)
        finally:
            if os.path.exists(logfile):
                os.remove(logfile)

    def test_log_forwarding_only_writes_file_handlers(self):
        class FailingHandler(logging.Handler):
            def emit(self, record):
                raise AssertionError('non-file handler should not be used')

        logfile = tempfile.mktemp(suffix='.log')
        log = logging.getLogger('test.netconf.forwarding')
        log.handlers.clear()
        log.setLevel(logging.INFO)
        log.propagate = False

        file_handler = logging.FileHandler(logfile)
        file_handler.setFormatter(yang.connector.netconf.NetconfFormatter())
        log.addHandler(FailingHandler())
        log.addHandler(file_handler)

        try:
            record = logging.LogRecord(
                'unicon.sshutils', logging.INFO, __file__, 0,
                'Adding local tunnel %s', ('127.0.0.1:123',), None)
            handler = yang.connector.netconf.NetconfLogForwardingHandler(log)
            handler.emit(record)

            with open(logfile) as log_file:
                log_content = log_file.read()

            self.assertIn('Adding local tunnel 127.0.0.1:123', log_content)
        finally:
            for handler in log.handlers[:]:
                log.removeHandler(handler)
                handler.close()
            if os.path.exists(logfile):
                os.remove(logfile)

    def test_configure_logging_skips_unavailable_tasklog(self):
        from pyats.log import managed_handlers

        logfile = tempfile.mktemp(suffix='.log')
        nc_device = yang.connector.Netconf(device=self.device,
                                           alias='nc',
                                           via='netconf',
                                           logfile=logfile,
                                           log_stdout=False)
        original_stream = managed_handlers.tasklog.stream

        try:
            managed_handlers.tasklog.stream = None
            nc_device.configure_logging()

            tasklog_handlers = [
                handler for handler in nc_device.log.handlers
                if isinstance(
                    handler,
                    yang.connector.netconf.pyATS_TaskLog_Adapter)
            ]
            self.assertEqual(tasklog_handlers, [])

            nc_device.log.info('tasklog stream unavailable')
        finally:
            managed_handlers.tasklog.stream = original_stream
            for handler in nc_device.log.handlers[:]:
                nc_device.log.removeHandler(handler)
                handler.close()
            if os.path.exists(logfile):
                os.remove(logfile)

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
