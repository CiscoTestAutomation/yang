import unittest
from unittest.mock import Mock, MagicMock, patch

from yang.connector import proto
from yang.connector import gnmi
from yang.connector import xpath_util

from pyats.topology import loader
from pyats.datastructures import AttrDict

from cryptography import x509
from cryptography.hazmat.backends import default_backend

class TestGnmi(unittest.TestCase):


    def test_connect(self):

        yaml = \
            'devices:\n' \
            '    dummy:\n' \
            '        type: dummy_device\n' \
            '        connections:\n' \
            '            Gnmi:\n' \
            '                class:  yang.connector.Gnmi\n' \
            '                protocol: gnmi\n' \
            '                ip : "1.2.3.4"\n' \
            '                port: 830\n' \
            '                username: admin\n' \
            '                password: admin\n' \

        testbed = loader.load(yaml)
        device = testbed.devices['dummy']
        with patch('yang.connector.gnmi.grpc.insecure_channel') as mock_grpc:
            device.connect(alias='gnmi', via='Gnmi')
            mock_grpc.assert_called_with('1.2.3.4:830', [('grpc.max_receive_message_length', 1000000000), ('grpc.max_send_message_length', 1000000000)])

    def test_re_connect(self):

        yaml = \
            'devices:\n' \
            '    dummy:\n' \
            '        type: dummy_device\n' \
            '        connections:\n' \
            '            Gnmi:\n' \
            '                class:  yang.connector.Gnmi\n' \
            '                protocol: gnmi\n' \
            '                ip : "1.2.3.4"\n' \
            '                port: 830\n' \
            '                username: admin\n' \
            '                password: admin\n' \

        testbed = loader.load(yaml)
        device = testbed.devices['dummy']
        with patch('yang.connector.gnmi.grpc.insecure_channel') as mock_grpc:
            device.connect()
            mock_grpc.assert_called_with('1.2.3.4:830', [('grpc.max_receive_message_length', 1000000000), ('grpc.max_send_message_length', 1000000000)])
            device.disconnect()
            device.connect(alias='gnmi', via='Gnmi')
            mock_grpc.assert_called_with('1.2.3.4:830', [('grpc.max_receive_message_length', 1000000000), ('grpc.max_send_message_length', 1000000000)])

    def test_connect_proxy(self):
        yaml = \
            'devices:\n' \
            '    dummy:\n' \
            '        type: proxy_device\n' \
            '        connections:\n' \
            '           defaults:\n' \
            '                class:  unicon.Unicon\n' \
            '           ssh:\n' \
            '                ip : "4.3.2.1"\n' \
            '                port: 22\n' \
            '                ssh_options: -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null\n' \
            '                password: admin\n' \
            '    dummy:\n' \
            '        type: dummy_device\n' \
            '        connections:\n' \
            '            Gnmi:\n' \
            '                class:  yang.connector.Gnmi\n' \
            '                protocol: gnmi\n' \
            '                ip : "1.2.3.4"\n' \
            '                port: 830\n' \
            '                username: admin\n' \
            '                password: admin\n' \
            '                sshtunnel:\n' \
            '                  host: jumphost\n'\
            '                  tunnel_ip: 830\n' \

        testbed = loader.load(yaml)
        device = testbed.devices['dummy']
        with patch('yang.connector.gnmi.sshtunnel.auto_tunnel_add') as mock_tunnel:
            with patch('yang.connector.gnmi.grpc.insecure_channel') as mock_grpc:
                mock_tunnel.side_effect = ['830']
                device.connections['Gnmi'].sshtunnel = AttrDict({'tunnel_ip': '4.3.2.1'})
                device.connect(alias='gnmi', via='Gnmi')
                mock_grpc.assert_called_with('4.3.2.1:830', [('grpc.max_receive_message_length', 1000000000), ('grpc.max_send_message_length', 1000000000)])
    request = {
        "namespace": {"oc-acl": "http://openconfig.net/yang/acl"},
        "nodes": [
            {
                "value": "testacl",
                "xpath": "/oc-acl:acl/oc-acl:acl-sets/oc-acl:acl-set/name",
                "edit-op": "merge",
            },
            {
                "value": "ACL_IPV4",
                "xpath": "/oc-acl:acl/oc-acl:acl-sets/oc-acl:acl-set/type",
                "edit-op": "merge",
            },
            {
                "value": "10",
                "xpath": '/oc-acl:acl/oc-acl:acl-sets/oc-acl:acl-set[name="testacl"][type="ACL_IPV4"]/oc-acl:acl-entries/oc-acl:acl-entry/oc-acl:sequence-id',
                "edit-op": "merge",
            },
            {
                "value": "20.20.20.1/32",
                "xpath": '/oc-acl:acl/oc-acl:acl-sets/oc-acl:acl-set[name="testacl"][type="ACL_IPV4"]/oc-acl:acl-entries/oc-acl:acl-entry[sequence-id="10"]/oc-acl:ipv4/oc-acl:config/oc-acl:destination-address',
                "edit-op": "merge",
            },
            {
                "value": "IP_TCP",
                "xpath": '/oc-acl:acl/oc-acl:acl-sets/oc-acl:acl-set[name="testacl"][type="ACL_IPV4"]/oc-acl:acl-entries/oc-acl:acl-entry[sequence-id="10"]/oc-acl:ipv4/oc-acl:config/oc-acl:protocol',
                "edit-op": "merge",
            },
            {
                "value": "10.10.10.10/32",
                "xpath": '/oc-acl:acl/oc-acl:acl-sets/oc-acl:acl-set[name="testacl"][type="ACL_IPV4"]/oc-acl:acl-entries/oc-acl:acl-entry[sequence-id="10"]/oc-acl:ipv4/oc-acl:config/oc-acl:source-address',
                "edit-op": "merge",
            },
            {
                "value": "DROP",
                "xpath": '/oc-acl:acl/oc-acl:acl-sets/oc-acl:acl-set[name="testacl"][type="ACL_IPV4"]/oc-acl:acl-entries/oc-acl:acl-entry[sequence-id="10"]/oc-acl:actions/oc-acl:config/oc-acl:forwarding-action',
                "edit-op": "merge",
            },
        ],
    }

    @patch('yang.connector.gnmi.grpc.secure_channel')
    @patch('yang.connector.gnmi.grpc.composite_channel_credentials')
    @patch('yang.connector.gnmi.grpc.metadata_call_credentials')
    @patch('yang.connector.gnmi.grpc.ssl_channel_credentials')
    @patch('yang.connector.gnmi.x509.load_pem_x509_certificate')
    @patch('yang.connector.gnmi.ssl.get_server_certificate')
    def test_connect_with_skip_verify(
        self, mock_get_server_certificate, mock_load_pem_x509_certificate,
        mock_ssl_channel_credentials, mock_metadata_call_credentials,
        mock_composite_channel_credentials, mock_secure_channel, *_
    ):
        yaml = """
devices:
    dummy:
        type: dummy_device
        connections:
            Gnmi:
                class:  yang.connector.Gnmi
                protocol: gnmi
                ip : 1.2.3.4
                port: 830
                username: admin
                password: admin
                skip_verify: true
"""
        testbed = loader.load(yaml)
        device = testbed.devices['dummy']
        device.connect(alias='gnmi', via='Gnmi')
        mock_get_server_certificate.assert_called_once_with(('1.2.3.4', '830'))
        mock_load_pem_x509_certificate.assert_called_once_with(
            mock_get_server_certificate.return_value.encode('utf-8'),
            default_backend()
        )
        mock_load_pem_x509_certificate.return_value.subject.get_attributes_for_oid.assert_called_once_with(
            (x509.NameOID.COMMON_NAME)
        )
        mock_ssl_channel_credentials.assert_called_once_with(
            mock_get_server_certificate.return_value.encode('utf-8'), None, None
        )
        self.assertEqual(
            mock_secure_channel.call_args[0][2][-1],
            (
                'grpc.ssl_target_name_override',
                mock_load_pem_x509_certificate.return_value.subject.get_attributes_for_oid.return_value[0].value
            )
        )

    @patch('yang.connector.gnmi.ssl.get_server_certificate', side_effect=Exception)
    def test_connect_with_skip_verify_get_server_certificate_exception(self, *_):
        yaml = """
devices:
    dummy:
        type: dummy_device
        connections:
            Gnmi:
                class:  yang.connector.Gnmi
                protocol: gnmi
                ip: 1.2.3.4
                port: 830
                username: admin
                password: admin
                skip_verify: true
"""
        testbed = loader.load(yaml)
        device = testbed.devices['dummy']
        with self.assertRaises(Exception):
            device.connect(alias='gnmi', via='Gnmi')

    @patch('yang.connector.gnmi.ssl.get_server_certificate')
    @patch('yang.connector.gnmi.grpc.insecure_channel')
    @patch('yang.connector.gnmi.x509.load_pem_x509_certificate')
    def test_connect_with_skip_verify_get_attributes_for_oid_exception(
        self, mock_load_pem_x509_certificate, mock_insecure_channel, *_
    ):
        yaml = """
devices:
    dummy:
        type: dummy_device
        connections:
            Gnmi:
                class:  yang.connector.Gnmi
                protocol: gnmi
                ip: 1.2.3.4
                port: 830
                username: admin
                password: admin
                skip_verify: true
"""
        mock_load_pem_x509_certificate.return_value.subject.get_attributes_for_oid.side_effect = BaseException
        testbed = loader.load(yaml)
        device = testbed.devices['dummy']
        device.connect(alias='gnmi', via='Gnmi')
        mock_insecure_channel.assert_called_once_with(
            '1.2.3.4:830', [
                ('grpc.max_receive_message_length', 1000000000),
                ('grpc.max_send_message_length', 1000000000)
            ]
        )

    def test_xpath_to_path_elem(self):
        """Test converting Genie content data to cisco_gnmi format."""
        modules, message, origin = xpath_util.xml_path_to_path_elem(self.request)
        self.assertEqual(modules, {'oc-acl': 'openconfig-acl'})
        self.assertEqual(message.get('delete'), [])
        self.assertEqual(message.get('get'), [])
        self.assertEqual(message.get('replace'), [])
        self.assertEqual(
            message.get('update'),
            [
                {'/acl/acl-sets/acl-set': {'name': 'testacl'}},
                {'/acl/acl-sets/acl-set': {'type': 'ACL_IPV4'}},
                {'/acl/acl-sets/acl-set[name="testacl"][type="ACL_IPV4"]/acl-entries/acl-entry': {'sequence-id': '10'}},
                {'/acl/acl-sets/acl-set[name="testacl"][type="ACL_IPV4"]/acl-entries/acl-entry[sequence-id="10"]/ipv4/config': {'destination-address': '20.20.20.1/32'}},
                {'/acl/acl-sets/acl-set[name="testacl"][type="ACL_IPV4"]/acl-entries/acl-entry[sequence-id="10"]/ipv4/config': {'protocol': 'IP_TCP'}},
                {'/acl/acl-sets/acl-set[name="testacl"][type="ACL_IPV4"]/acl-entries/acl-entry[sequence-id="10"]/ipv4/config': {'source-address': '10.10.10.10/32'}},
                {'/acl/acl-sets/acl-set[name="testacl"][type="ACL_IPV4"]/acl-entries/acl-entry[sequence-id="10"]/actions/config': {'forwarding-action': 'DROP'}}
            ]
        )
        self.assertEqual(origin, 'openconfig')

    def test_get_prefix(self):
        """Test creating a prefix Path gNMI class."""
        path = xpath_util.get_prefix('rfc7951')
        self.assertIsInstance(path, proto.gnmi_pb2.Path)

    def test_connect_grcp_length(self):
        yaml = \
            'devices:\n' \
            '    dummy:\n' \
            '        type: dummy_device\n' \
            '        connections:\n' \
            '            Gnmi:\n' \
            '                class:  yang.connector.Gnmi\n' \
            '                protocol: gnmi\n' \
            '                ip : "1.2.3.4"\n' \
            '                port: 830\n' \
            '                username: admin\n' \
            '                password: admin\n' \
            '                settings:\n' \
            '                  GRPC_MAX_RECEIVE_MESSAGE_LENGTH: 100\n' \
            '                  GRPC_MAX_SEND_MESSAGE_LENGTH: 100\n' \

        testbed = loader.load(yaml)
        device = testbed.devices['dummy']
        with patch('yang.connector.gnmi.grpc.insecure_channel') as mock_grpc:
            device.connect(alias='gnmi', via='Gnmi')
            mock_grpc.assert_called_with('1.2.3.4:830', [('grpc.max_receive_message_length', 100), ('grpc.max_send_message_length', 100)])


if __name__ == '__main__':
    unittest.main()
