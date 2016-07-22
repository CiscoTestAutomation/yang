#!/bin/env python
""" Unit tests for the yang cisco-shared package. """

import unittest
import socket
import paramiko
from ats.topology import loader
from ats.connections import BaseConnection
from unittest.mock import Mock, patch
import yang.connector

class MyChannel_1():

    def __init__(self):
        self.buffer = 'abcdefghijk'

    def recv_ready(self):
        if self.buffer:
            return True
        else:
            return False

    def recv(self, number):
        if len(self.buffer) > 3:
            ret = self.buffer[:3]
            self.buffer = self.buffer[3:]
            return ret.encode()
        else:
            ret = self.buffer
            self.buffer = ''
            return ret.encode()

    def sendall(self, message):
        pass

    def settimeout(self, int):
        pass

    def close(self):
        pass

class MyChannel_2():

    def __init__(self):
        self.buffer = 'abcdefghijk'

    def sendall(self, message):
        raise socket.error('socket error')

class MySsh():

    def close(self):
        pass

class MySocket():

    def close(self):
        pass

class MockSocket():

    def __init__(self, family, addr_type, protocol):
        raise socket.error('fake error')

    def getaddrinfo(self, ip, port, family='', type=''):
        return [('', '', '', '', '')]

    def socket(self, family, addr_type, protocol):
        return self

    def settimeout(self, timeout):
        pass

    def connect(self, sock_addr):
        pass

    def close(self):
        pass

class MockParamiko1():

    def __init__(self, socket):
        self.buffer = \
            '<?xml version="1.0" encoding="UTF-8"?>' \
            '<hello xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">' \
            '<capabilities>' \
            '<capability>urn:ietf:params:netconf:base:1.0</capability>' \
            '<capability>urn:ietf:params:netconf:base:1.1</capability>' \
            '</capabilities>' \
            '<session-id>20</session-id></hello>]]>]]>'

    def connect(self, hostkey='', username='', password=''):
        pass

    def open_session(self):
        return self

    def invoke_subsystem(self, subsystem):
        pass

    def settimeout(self, timeout):
        pass

    def recv_ready(self):
        if self.buffer:
            return True
        else:
            return False

    def recv(self, number):
        if len(self.buffer) > 3:
            ret = self.buffer[:3]
            self.buffer = self.buffer[3:]
            return ret.encode()
        else:
            ret = self.buffer
            self.buffer = ''
            return ret.encode()

    def sendall(self, message):
        pass

class MockParamiko2():

    def __init__(self, socket):
        self.buffer = \
            '<?xml version="1.0" encoding="UTF-8"?>' \
            '<hello xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">' \
            '<capabilities>' \
            '<capability>urn:ietf:params:netconf:base:1.0</capability>' \
            '<capability>urn:ietf:params:netconf:base:1.1</capability>' \
            '</capabilities>' \
            '<session-id>20</session-id></hello>]]>]]>'

    def connect(self, hostkey='', username='', password=''):
        raise paramiko.AuthenticationException('fake error')

    def open_session(self):
        return self

    def invoke_subsystem(self, subsystem):
        pass

    def settimeout(self, timeout):
        pass

    def recv_ready(self):
        if self.buffer:
            return True
        else:
            return False

    def recv(self, number):
        if len(self.buffer) > 3:
            ret = self.buffer[:3]
            self.buffer = self.buffer[3:]
            return ret.encode()
        else:
            ret = self.buffer
            self.buffer = ''
            return ret.encode()

    def sendall(self, message):
        pass

class MockParamiko3():

    def __init__(self, socket):
        self.buffer = \
            '<?xml version="1.0" encoding="UTF-8"?>' \
            '<hello xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">' \
            '<capabilities>' \
            '<capability>urn:ietf:params:netconf:base:1.0</capability>' \
            '</capabilities>' \
            '<session-id>20</session-id></hello>]]>]]>'

    def connect(self, hostkey='', username='', password=''):
        pass

    def open_session(self):
        return self

    def invoke_subsystem(self, subsystem):
        pass

    def settimeout(self, timeout):
        pass

    def recv_ready(self):
        if self.buffer:
            return True
        else:
            return False

    def recv(self, number):
        if len(self.buffer) > 3:
            ret = self.buffer[:3]
            self.buffer = self.buffer[3:]
            return ret.encode()
        else:
            ret = self.buffer
            self.buffer = ''
            return ret.encode()

    def sendall(self, message):
        pass

class MockParamiko4():

    def __init__(self, socket):
        self.buffer = \
            '<?xml version="1.0" encoding="UTF-8"?>' \
            '<hello xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">' \
            '<capabilities>' \
            '<capability>urn:ietf:params:netconf:base:1.2</capability>' \
            '</capabilities>' \
            '<session-id>20</session-id></hello>]]>]]>'

    def connect(self, hostkey='', username='', password=''):
        pass

    def open_session(self):
        return self

    def invoke_subsystem(self, subsystem):
        pass

    def settimeout(self, timeout):
        pass

    def recv_ready(self):
        if self.buffer:
            return True
        else:
            return False

    def recv(self, number):
        if len(self.buffer) > 3:
            ret = self.buffer[:3]
            self.buffer = self.buffer[3:]
            return ret.encode()
        else:
            ret = self.buffer
            self.buffer = ''
            return ret.encode()

    def sendall(self, message):
        pass

class TestYang(unittest.TestCase):

    def setUp(self):
        self.test_input_string_1 = \
            '<?xml version="1.0" encoding="UTF-8"?>\n' \
            '<rpc-reply ' \
            'xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="101">' \
            '<data><native xmlns="urn:ios"><version>15.6</version></native></data>' \
            '</rpc-reply>]]>]]>'
        self.test_input_string_2 = \
            '\n#196\n<?xml version="1.0" encoding="UTF-8"?>\n' \
            '<rpc-reply ' \
            'xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="101">' \
            '<data><native xmlns="urn:ios"><version>15.6</version></native></data>' \
            '</rpc-reply>\n##\n'
        self.test_input_string_3 = \
            '\n#184\n<?xml version="1.0" encoding="UTF-8"?>\n' \
            '<rpc-reply ' \
            'xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="101">' \
            '<data><native xmlns="urn:ios"><version>15.6</version></native></data>' \
            '\n#12\n</rpc-reply>\n##\n'
        self.test_input_string_4 = \
            '\n#4\n' \
            '<rpc' \
            '\n#18\n' \
            ' message-id="102"\n' \
            '\n#79\n' \
            '     xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">\n' \
            '  <close-session/>\n' \
            '</rpc>' \
            '\n##\n'
        self.test_input_wrong_1 = \
            '<?xml'
        self.test_input_wrong_2 = \
            '\n#196'
        self.test_input_wrong_3 = \
            '\n#196\n<?xml version="1.0" encoding="UTF-8"?>\n' \
            '<rpc-reply ' \
            'xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="101">' \
            '<data><native xmlns="urn:ios"><version>15.6</version></native></data>' \
            '</rpc-reply>\n##'
        self.test_input_wrong_4 = \
            '\n#196\n<?xml version="1.0" encoding="UTF-8"?>\n' \
            '<rpc-reply ' \
            'xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="101">' \
            '<data><native xmlns="urn:ios"><version>15.6</version></native></data>' \
            '</rpc-reply>\n##\n\n'
        self.test_input_wrong_5 = \
            '\n#196aaaaabbbbbccccc'
        self.test_input_wrong_6 = \
            '\n#196\n<?xml version="1.0" encoding="UTF-8"?>\n' \
            '<rpc-reply ' \
            'xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="101">' \
            '<data><native xmlns="urn:ios"><version>15.6</version></native></data>' \
            '</rpc-reply>\n##k'
        self.test_output_string_1 = \
            '<?xml version="1.0" encoding="UTF-8"?>\n' \
            '<rpc-reply ' \
            'xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="101">' \
            '<data><native xmlns="urn:ios"><version>15.6</version></native></data>' \
            '</rpc-reply>'
        self.test_output_string_2 = \
            '<rpc message-id="102"\n' \
            '     xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">\n' \
            '  <close-session/>\n' \
            '</rpc>'
        self.yaml = \
            'devices:\n' \
            '    dummy:\n' \
            '        type: dummy_device\n' \
            '        connections:\n' \
            '            netconf:\n' \
            '                class: yang.connector.Netconf\n' \
            '                protocol : netconf\n' \
            '                ip : "1.2.3.4"\n' \
            '                port: 2022\n' \
            '                user: admin\n' \
            '                password: admin\n'
        self.yaml_wrong_1 = \
            'devices:\n' \
            '    dummy:\n' \
            '        type: dummy_device\n' \
            '        connections:\n' \
            '            netconf:\n' \
            '                protocol : netconf\n' \
            '                ip : "1.2.3.4"\n' \
            '                port: 2022\n' \
            '                user: admin\n' \
            '                password: admin\n'
        self.yaml_wrong_2 = \
            'devices:\n' \
            '    dummy:\n' \
            '        type: dummy_device\n' \
            '        connections:\n' \
            '            netconf:\n' \
            '                class: yang.connector.Netconf\n' \
            '                ip : "1.2.3.4"\n' \
            '                port: 2022\n' \
            '                user: admin\n' \
            '                password: admin\n'
        self.yaml_wrong_3 = \
            'devices:\n' \
            '    dummy:\n' \
            '        type: dummy_device\n' \
            '        connections:\n' \
            '            netconf:\n' \
            '                class: yang.connector.Netconf\n' \
            '                protocol : net\n' \
            '                ip : "1.2.3.4"\n' \
            '                port: 2022\n' \
            '                user: admin\n' \
            '                password: admin\n'
        self.yaml_wrong_4 = \
            'devices:\n' \
            '    dummy:\n' \
            '        type: dummy_device\n' \
            '        connections:\n' \
            '            netconf:\n' \
            '                class: yang.connector.Netconf\n' \
            '                protocol : netconf\n' \
            '                port: 2022\n' \
            '                user: admin\n' \
            '                password: admin\n'
        self.yaml_wrong_5 = \
            'devices:\n' \
            '    dummy:\n' \
            '        type: dummy_device\n' \
            '        connections:\n' \
            '            netconf:\n' \
            '                class: yang.connector.Netconf\n' \
            '                protocol : netconf\n' \
            '                ip : "1.2.3.4"\n' \
            '                user: admin\n' \
            '                password: admin\n'
        self.yaml_wrong_6 = \
            'devices:\n' \
            '    dummy:\n' \
            '        type: dummy_device\n' \
            '        connections:\n' \
            '            netconf:\n' \
            '                class: yang.connector.Netconf\n' \
            '                protocol : netconf\n' \
            '                ip : "1.2.3.4"\n' \
            '                port: 2022\n' \
            '                password: admin\n'
        self.yaml_wrong_7 = \
            'devices:\n' \
            '    dummy:\n' \
            '        type: dummy_device\n' \
            '        connections:\n' \
            '            netconf:\n' \
            '                class: yang.connector.Netconf\n' \
            '                protocol : netconf\n' \
            '                ip : "1.2.3.4"\n' \
            '                port: 2022\n' \
            '                user: admin\n'

        self.testbed = loader.load(self.yaml)
        self.device = self.testbed.devices['dummy']
        self.nc_device = yang.connector.Netconf(device=self.device,
                                                alias='nc', via='netconf')

    def test_validate_1(self):
        self.nc_device.framing = '1.0'
        generated_text = self.nc_device._validate(self.test_input_string_1)
        expected_text = self.test_output_string_1
        self.assertEqual(generated_text, expected_text)

    def test_validate_2(self):
        self.nc_device.framing = '1.1'
        generated_text = self.nc_device._validate(self.test_input_string_2)
        expected_text = self.test_output_string_1
        self.assertEqual(generated_text, expected_text)

    def test_validate_3(self):
        self.nc_device.framing = '1.1'
        generated_text = self.nc_device._validate(self.test_input_string_3)
        expected_text = self.test_output_string_1
        self.assertEqual(generated_text, expected_text)

    def test_validate_3(self):
        self.nc_device.framing = '1.1'
        generated_text = self.nc_device._validate(self.test_input_string_4)
        expected_text = self.test_output_string_2
        self.assertEqual(generated_text, expected_text)

    def test_validate_error_1(self):
        self.nc_device.framing = '1.0'
        generated_value = self.nc_device._validate(self.test_input_wrong_1)
        expected_value = None
        self.assertEqual(generated_value, expected_value)

    def test_validate_error_2(self):
        self.nc_device.framing = '1.1'
        generated_value = self.nc_device._validate(self.test_input_wrong_2)
        expected_value = None
        self.assertEqual(generated_value, expected_value)

    def test_validate_error_3(self):
        self.nc_device.framing = '1.1'
        generated_value = self.nc_device._validate(self.test_input_wrong_3)
        expected_value = None
        self.assertEqual(generated_value, expected_value)

    def test_validate_error_4(self):
        self.nc_device.framing = '1.1'
        generated_value = self.nc_device._validate(self.test_input_wrong_4)
        expected_value = None
        self.assertEqual(generated_value, expected_value)

    def test_validate_error_5(self):
        self.nc_device.framing = '1.1'
        generated_value = self.nc_device._validate(self.test_input_wrong_5)
        expected_value = None
        self.assertEqual(generated_value, expected_value)

    def test_validate_error_6(self):
        self.nc_device.framing = '1.1'
        generated_value = self.nc_device._validate(self.test_input_wrong_6)
        expected_value = None
        self.assertEqual(generated_value, expected_value)

    def test_validate_error_7(self):
        self.nc_device.framing = '1.2'
        self.assertRaises(Exception,
                          self.nc_device._validate,
                          self.test_input_string_2)

    def test_init(self):
        testbed = loader.load(self.yaml)
        device = testbed.devices['dummy']
        nc_dev = yang.connector.Netconf(device=self.device, alias='nc',
                                        via='netconf',
                                        bufsize=10240, timeout=11)
        generated_value = nc_dev.bufsize
        expected_value = 10240
        self.assertEqual(generated_value, expected_value)
        generated_value = nc_dev.timeout
        expected_value = 11
        self.assertEqual(generated_value, expected_value)

    def test_init_error_1(self):
        testbed = loader.load(self.yaml_wrong_1)
        device = testbed.devices['dummy']
        self.assertRaises(Exception,
                          yang.connector.Netconf,
                          device=device, alias='nc', via='netconf')

    def test_init_error_2(self):
        testbed = loader.load(self.yaml_wrong_2)
        device = testbed.devices['dummy']
        self.assertRaises(Exception,
                          yang.connector.Netconf,
                          device=device, alias='nc', via='netconf')

    def test_init_error_3(self):
        testbed = loader.load(self.yaml_wrong_3)
        device = testbed.devices['dummy']
        self.assertRaises(Exception,
                          yang.connector.Netconf,
                          device=device, alias='nc', via='netconf')

    def test_init_error_4(self):
        testbed = loader.load(self.yaml_wrong_4)
        device = testbed.devices['dummy']
        self.assertRaises(Exception,
                          yang.connector.Netconf,
                          device=device, alias='nc', via='netconf')

    def test_init_error_5(self):
        testbed = loader.load(self.yaml_wrong_5)
        device = testbed.devices['dummy']
        self.assertRaises(Exception,
                          yang.connector.Netconf,
                          device=device, alias='nc', via='netconf')

    def test_init_error_6(self):
        testbed = loader.load(self.yaml_wrong_6)
        device = testbed.devices['dummy']
        self.assertRaises(Exception,
                          yang.connector.Netconf,
                          device=device, alias='nc', via='netconf')

    def test_init_error_7(self):
        testbed = loader.load(self.yaml_wrong_7)
        device = testbed.devices['dummy']
        self.assertRaises(Exception,
                          yang.connector.Netconf,
                          device=device, alias='nc', via='netconf')

    def test_connect_1(self):
        self.nc_device.channel = MyChannel_1()
        self.nc_device.connect()

    def test_connect_2(self):
        self.nc_device.timeout = 1
        self.assertRaises(Exception,
                          self.nc_device.connect)

    @patch.object(socket, 'socket', autospec=True)
    @patch('paramiko.Transport', new=MockParamiko1)
    def test_connect_3(self, socket_mock):
        socket_mock.getaddrinfo = Mock()
        socket_mock.getaddrinfo.return_value=[('', '', '', '', '')]
        socket_mock.socket = Mock()
        socket_mock.socket.return_value=socket_mock
        self.device.connect(alias='nc', via='netconf')
        generated_value = self.device.nc.connected
        expected_value = True
        self.assertEqual(generated_value, expected_value)

    @patch('socket.socket', new=MockSocket)
    def test_connect_4(self):
        self.assertRaises(Exception,
                          self.device.connect,
                          alias='nc', via='netconf')

    @patch.object(socket, 'socket', autospec=True)
    @patch('paramiko.Transport', new=MockParamiko2)
    def test_connect_5(self, socket_mock):
        socket_mock.getaddrinfo = Mock()
        socket_mock.getaddrinfo.return_value=[('', '', '', '', '')]
        socket_mock.socket = Mock()
        socket_mock.socket.return_value=socket_mock
        self.assertRaises(Exception,
                          self.device.connect,
                          alias='nc', via='netconf')

    @patch.object(socket, 'socket', autospec=True)
    @patch('paramiko.Transport', new=MockParamiko3)
    def test_connect_6(self, socket_mock):
        socket_mock.getaddrinfo = Mock()
        socket_mock.getaddrinfo.return_value=[('', '', '', '', '')]
        socket_mock.socket = Mock()
        socket_mock.socket.return_value=socket_mock
        self.device.connect(alias='nc', via='netconf')
        generated_value = self.device.nc.connected
        expected_value = True
        self.assertEqual(generated_value, expected_value)

    @patch.object(socket, 'socket', autospec=True)
    @patch('paramiko.Transport', new=MockParamiko4)
    def test_connect_7(self, socket_mock):
        socket_mock.getaddrinfo = Mock()
        socket_mock.getaddrinfo.return_value=[('', '', '', '', '')]
        socket_mock.socket = Mock()
        socket_mock.socket.return_value=socket_mock
        self.assertRaises(Exception,
                          self.device.connect,
                          alias='nc', via='netconf')

    def test_connected_1(self):
        generated_value = self.nc_device.connected
        expected_value = False
        self.assertEqual(generated_value, expected_value)

    def test_connected_2(self):
        self.nc_device.channel = MyChannel_1()
        generated_value = self.nc_device.connected
        expected_value = True
        self.assertEqual(generated_value, expected_value)

    def test_config(self):
        self.assertRaises(Exception,
                          self.nc_device.configure,
                          'logging console')

    def test_execute(self):
        self.assertRaises(Exception,
                          self.nc_device.execute,
                          'show version')

    def test_receive_1(self):
        self.nc_device.channel = MyChannel_1()
        generated_value = self.nc_device._receive()
        expected_value = 'abcdefghijk'
        self.assertEqual(generated_value, expected_value)

    def test_receive_2(self):
        self.nc_device.framing = '1.0'
        self.nc_device.channel = MyChannel_1()
        self.nc_device.channel.buffer = self.test_input_string_1
        generated_value = self.nc_device.receive()
        expected_value = self.test_output_string_1
        self.assertEqual(generated_value, expected_value)

    def test_receive_3(self):
        self.nc_device.framing = '1.0'
        self.nc_device.timeout = 1
        self.nc_device.channel = MyChannel_1()
        self.assertRaises(Exception,
                          self.nc_device.receive)

    def test_receive_4(self):
        self.nc_device.channel = None
        self.assertRaises(Exception,
                          self.nc_device._receive)

    def test_receive_5(self):
        self.nc_device.channel = None
        self.assertRaises(Exception,
                          self.nc_device.receive)

    def test_send_1(self):
        self.nc_device.channel = MyChannel_1()
        self.nc_device.bufsize = 3
        self.nc_device._send('abcdefghijk')

    def test_send_2(self):
        self.nc_device.channel = MyChannel_2()
        self.assertRaises(Exception,
                          self.nc_device._send,
                          'abcdefghijk')

    def test_send_3(self):
        self.nc_device.framing = '1.0'
        self.nc_device.channel = MyChannel_1()
        self.nc_device.bufsize = 3
        self.nc_device.send('abcdefghijk')

    def test_send_4(self):
        self.nc_device.framing = '1.1'
        self.nc_device.channel = MyChannel_1()
        self.nc_device.bufsize = 3
        self.nc_device.send('abcdefghijk')

    def test_send_5(self):
        self.nc_device.framing = '1.2'
        self.nc_device.channel = MyChannel_1()
        self.assertRaises(Exception,
                          self.nc_device.send,
                          'abcdefghijk')

    def test_send_6(self):
        self.nc_device.channel = None
        self.assertRaises(Exception,
                          self.nc_device._send,
                          'abcdefghijk')

    def test_send_7(self):
        self.nc_device.framing = '1.0'
        self.nc_device.channel = None
        self.assertRaises(Exception,
                          self.nc_device.send,
                          'abcdefghijk')

    def test_request_1(self):
        self.nc_device.framing = '1.0'
        self.nc_device.channel = None
        self.assertRaises(Exception,
                          self.nc_device.request,
                          'abcdefghijk')

    def test_request_2(self):
        self.nc_device.framing = '1.0'
        self.nc_device.channel = MyChannel_1()
        self.nc_device.channel.buffer = self.test_input_string_1
        generated_value = self.nc_device.request('hello', timeout=11)
        expected_value = self.test_output_string_1
        self.assertEqual(generated_value, expected_value)

    def test_disconnect(self):
        self.nc_device.channel = MyChannel_1()
        self.nc_device.ssh = MySsh()
        self.nc_device.socket = MySocket()
        self.nc_device.disconnect()
        generated_value = self.nc_device.channel
        expected_value = None
        self.assertEqual(generated_value, expected_value)
        generated_value = self.nc_device.ssh
        expected_value = None
        self.assertEqual(generated_value, expected_value)
        generated_value = self.nc_device.socket
        expected_value = None
        self.assertEqual(generated_value, expected_value)
        generated_value = self.nc_device.framing
        expected_value = '1.0'
        self.assertEqual(generated_value, expected_value)
        generated_value = self.nc_device.capabilities
        expected_value = ''
        self.assertEqual(generated_value, expected_value)
