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
from unittest.mock import Mock, call, patch
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

    @property
    def id(self):
        return None

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

    @property
    def id(self):
        return None

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
        tunnel_logger = logging.getLogger('unicon.sshutils')
        original_tunnel_level = tunnel_logger.level

        nc_device = yang.connector.Netconf(device=device,
                                           alias='nc',
                                           via='netconf',
                                           logfile=logfile,
                                           log_stdout=False,
                                           no_pyats_tasklog=True)
        nc_device._session = MySSHSession()

        def add_tunnel(**kwargs):
            logging.getLogger('unicon.sshutils').info(
                'Adding local tunnel 127.0.0.1:%s', 123)
            return 123

        from unicon.sshutils import sshtunnel
        proxy_connection = Mock()
        try:
            tunnel_logger.setLevel(logging.WARNING)
            with patch.object(sshtunnel, 'connect_proxy_host'), \
                 patch.object(sshtunnel, 'add_tunnel',
                              side_effect=add_tunnel) as tunnel_add, \
                 patch.object(sshtunnel, 'proxy_connections',
                              {'proxy': proxy_connection}), \
                 patch.object(sshtunnel, 'remove_tunnel') as remove_tunnel:
                nc_device.connect()
                self.assertEqual(tunnel_add.call_args.kwargs['target_address'],
                                 '1.2.3.4')
                self.assertEqual(tunnel_add.call_args.kwargs['target_port'], 830)

                with open(logfile) as log_file:
                    log_content = log_file.read()

                self.assertIn('Adding local tunnel 127.0.0.1:123', log_content)
                self.assertIn('NETCONF CONNECTED', log_content)
                self.assertEqual(nc_device.session.connect_kwargs['host'],
                                 '127.0.0.1')
                self.assertEqual(nc_device.session.connect_kwargs['port'], 123)
                self.assertEqual(tunnel_logger.level, logging.WARNING)
                nc_device.disconnect()

                remove_tunnel.assert_called_once_with(
                    proxy_conn=proxy_connection,
                    tunnel_type='local',
                    tunnel_port=123,
                )
        finally:
            tunnel_logger.setLevel(original_tunnel_level)
            if os.path.exists(logfile):
                os.remove(logfile)

    def _load_dynamic_netconf_device(self, with_tunnel=True):
        tunnel_block = (
            '                sshtunnel:\n'
            '                    host: proxy\n'
            '                    tunnel_ip: 127.0.0.1\n'
            if with_tunnel else ''
        )
        yaml = (
            'devices:\n'
            '    qemu-uut:\n'
            '        os: iosxe\n'
            '        type: qemu\n'
            '        connections:\n'
            '            netconf:\n'
            '                class: yang.connector.Netconf\n'
            '                protocol: netconf\n'
            '                ip: 192.0.2.10\n'
            '                port: 830\n'
            '                username: admin\n'
            '                password: admin\n'
            + tunnel_block +
            '                tunnel_target:\n'
            '                    address: 10.0.2.15\n'
            '                qemu_usernet:\n'
            '                    qmp_socket_path: /tmp/qmp.sock\n'
            '                    guest_ip: 10.0.2.15\n'
            '                    netdev_id: Gi0\n'
        )
        device = loader.load(yaml).devices['qemu-uut']
        if with_tunnel:
            device.connections.netconf.sshtunnel = AttrDict(
                device.connections.netconf.sshtunnel)
        return device

    def test_runtime_port_and_qemu_metadata_without_tunnel(self):
        device = self._load_dynamic_netconf_device(with_tunnel=False)
        nc_device = yang.connector.Netconf(
            device=device, alias='dynamic', via='netconf', port=8830)
        nc_device._session = MySSHSession()

        nc_device.connect()

        self.assertEqual(nc_device.session.connect_kwargs['port'], 8830)
        self.assertNotIn('qemu_usernet', nc_device.session.connect_kwargs)
        self.assertNotIn('tunnel_target', nc_device.session.connect_kwargs)

    def test_runtime_effective_port_is_ssh_tunnel_target_and_owned_tunnel_is_removed(self):
        from unicon.sshutils import sshtunnel

        device = self._load_dynamic_netconf_device()
        nc_device = yang.connector.Netconf(
            device=device, alias='dynamic', via='netconf', port=43613)
        nc_device._session = MySSHSession()
        proxy_connection = Mock()

        with patch.object(sshtunnel, 'proxy_connections', {'proxy': proxy_connection}), \
             patch.object(sshtunnel, 'connect_proxy_host'), \
             patch.object(sshtunnel, 'add_tunnel', return_value=44001) as add_tunnel, \
             patch.object(sshtunnel, 'remove_tunnel') as remove_tunnel:
            nc_device.connect()

            self.assertEqual(add_tunnel.call_args.kwargs['target_address'],
                             '10.0.2.15')
            self.assertEqual(add_tunnel.call_args.kwargs['target_port'], 43613)
            self.assertEqual(nc_device.session.connect_kwargs['host'], '127.0.0.1')
            self.assertEqual(nc_device.session.connect_kwargs['port'], 44001)
            self.assertNotIn('qemu_usernet', nc_device.session.connect_kwargs)
            self.assertNotIn('tunnel_target', nc_device.session.connect_kwargs)
            self.assertTrue(nc_device._tunnel_owned)

            nc_device.disconnect()

            remove_tunnel.assert_called_once_with(
                proxy_conn=proxy_connection,
                tunnel_type='local',
                tunnel_port=44001,
            )
            self.assertFalse(nc_device._tunnel_owned)
            self.assertFalse(device.connections.netconf.sshtunnel.connected)

    def test_failed_netconf_session_rolls_back_created_tunnel(self):
        from unicon.sshutils import sshtunnel

        device = self._load_dynamic_netconf_device()
        nc_device = yang.connector.Netconf(
            device=device, alias='dynamic', via='netconf', port=43613)
        nc_device._session = MySSHSession()
        nc_device._session.connect = Mock(side_effect=RuntimeError('session failed'))
        proxy_connection = Mock()

        with patch.object(sshtunnel, 'proxy_connections', {'proxy': proxy_connection}), \
             patch.object(sshtunnel, 'connect_proxy_host'), \
             patch.object(sshtunnel, 'add_tunnel', return_value=44001), \
             patch.object(sshtunnel, 'remove_tunnel') as remove_tunnel:
            with self.assertRaisesRegex(RuntimeError, 'session failed'):
                nc_device.connect()

        remove_tunnel.assert_called_once_with(
            proxy_conn=proxy_connection,
            tunnel_type='local',
            tunnel_port=44001,
        )
        self.assertFalse(nc_device._tunnel_owned)

    def test_atexit_cleanup_removes_owned_tunnel(self):
        from unicon.sshutils import sshtunnel

        device = self._load_dynamic_netconf_device()
        nc_device = yang.connector.Netconf(
            device=device, alias='dynamic', via='netconf', port=43613)
        nc_device._session = MySSHSession()
        proxy_connection = Mock()

        with patch('atexit.register') as register, \
             patch.object(sshtunnel, 'proxy_connections', {'proxy': proxy_connection}), \
             patch.object(sshtunnel, 'connect_proxy_host'), \
             patch.object(sshtunnel, 'add_tunnel', return_value=44001), \
             patch.object(sshtunnel, 'remove_tunnel') as remove_tunnel:
            nc_device.connect()
            cleanup = register.call_args.args[0]
            cleanup()

        remove_tunnel.assert_called_once_with(
            proxy_conn=proxy_connection,
            tunnel_type='local',
            tunnel_port=44001,
        )
        self.assertFalse(nc_device._tunnel_owned)

    def test_adopted_tunnel_is_not_removed_by_connector(self):
        from unicon.sshutils import sshtunnel

        device = self._load_dynamic_netconf_device()
        device.connections.netconf.sshtunnel.connected = True
        device.connections.netconf.sshtunnel.tunnel_port = 44001
        device.connections.netconf.sshtunnel.target_address = '10.0.2.15'
        device.connections.netconf.sshtunnel.target_port = 43613
        nc_device = yang.connector.Netconf(
            device=device, alias='dynamic', via='netconf', port=43613)
        nc_device._session = MySSHSession()

        with patch.object(sshtunnel, 'add_tunnel') as add_tunnel, \
             patch.object(sshtunnel, 'remove_tunnel') as remove_tunnel:
            nc_device.connect()
            nc_device.disconnect()

        add_tunnel.assert_not_called()
        remove_tunnel.assert_not_called()
        self.assertFalse(nc_device._tunnel_owned)

    def test_existing_tunnel_with_different_target_port_is_replaced(self):
        from unicon.sshutils import sshtunnel

        device = self._load_dynamic_netconf_device()
        tunnel_config = device.connections.netconf.sshtunnel
        tunnel_config.connected = True
        tunnel_config.tunnel_port = 44001
        tunnel_config.target_address = '10.0.2.15'
        tunnel_config.target_port = 830
        nc_device = yang.connector.Netconf(
            device=device, alias='dynamic', via='netconf', port=43613)
        nc_device._session = MySSHSession()
        proxy_connection = Mock()

        with patch.object(sshtunnel, 'proxy_connections', {'proxy': proxy_connection}), \
             patch.object(sshtunnel, 'connect_proxy_host'), \
             patch.object(sshtunnel, 'remove_tunnel') as remove_tunnel, \
             patch.object(sshtunnel, 'add_tunnel', return_value=44002) as add_tunnel:
            nc_device.connect()
            nc_device.disconnect()

        self.assertEqual(remove_tunnel.call_args_list, [
            call(proxy_conn=proxy_connection, tunnel_type='local',
                 tunnel_port=44001),
            call(proxy_conn=proxy_connection, tunnel_type='local',
                 tunnel_port=44002),
        ])
        self.assertEqual(add_tunnel.call_args.kwargs['target_port'], 43613)
        self.assertEqual(nc_device.session.connect_kwargs['port'], 44002)
        self.assertFalse(nc_device._tunnel_owned)
        self.assertEqual(tunnel_config.target_port, 43613)

    def test_ncclient_session_logging(self):
        logfile = tempfile.mktemp(suffix='.log')
        ncclient_logger = logging.getLogger('ncclient')
        ncclient_ssh_logger = logging.getLogger('ncclient.transport.ssh')
        original_ncclient_level = ncclient_logger.level
        original_ncclient_ssh_level = ncclient_ssh_logger.level
        nc_device = yang.connector.Netconf(device=self.device,
                                           alias='nc',
                                           via='netconf',
                                           logfile=logfile,
                                           log_stdout=False,
                                           no_pyats_tasklog=True)
        nc_device._session = MySSHSession()

        try:
            ncclient_logger.setLevel(logging.WARNING)
            ncclient_ssh_logger.setLevel(logging.NOTSET)
            nc_device.connect()
            nc_device.session.logger.info(
                'Sending:\n%s', b'<hello/>',
                extra={'session': nc_device.session})

            with open(logfile) as log_file:
                log_content = log_file.read()

            self.assertIn('Sending:', log_content)
            self.assertIn('<hello/>', log_content)
            self.assertEqual(ncclient_logger.level, logging.WARNING)
            self.assertEqual(ncclient_ssh_logger.level, logging.NOTSET)
        finally:
            ncclient_logger.setLevel(original_ncclient_level)
            ncclient_ssh_logger.setLevel(original_ncclient_ssh_level)
            if os.path.exists(logfile):
                os.remove(logfile)

    def test_ncclient_debug_session_logging(self):
        logfile = tempfile.mktemp(suffix='.log')
        ncclient_logger = logging.getLogger('ncclient')
        original_ncclient_level = ncclient_logger.level
        nc_device = yang.connector.Netconf(device=self.device,
                                           alias='nc',
                                           via='netconf',
                                           logfile=logfile,
                                           log_stdout=False,
                                           no_pyats_tasklog=True,
                                           debug=True)
        nc_device._session = MySSHSession()

        try:
            ncclient_logger.setLevel(logging.WARNING)
            nc_device.connect()
            nc_device.session.logger.debug(
                'Received:\n%s', b'<rpc-reply/>',
                extra={'session': nc_device.session})

            with open(logfile) as log_file:
                log_content = log_file.read()

            self.assertIn('Received:', log_content)
            self.assertIn('<rpc-reply/>', log_content)
            self.assertEqual(ncclient_logger.level, logging.WARNING)
        finally:
            ncclient_logger.setLevel(original_ncclient_level)
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
