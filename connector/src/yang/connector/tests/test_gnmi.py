import unittest

from yang.connector import proto
from yang.connector import xpath_util


class TestXpathUtil(unittest.TestCase):

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

    def test_xpath_to_path_elem(self):
        """Test converting Genie content data to cisco_gnmi format."""
        modules, message, origin = xpath_util.xml_path_to_path_elem(self.request)
        self.assertEquals(modules, {'oc-acl': 'openconfig-acl'})
        self.assertEquals(message.get('delete'), [])
        self.assertEquals(message.get('get'), [])
        self.assertEquals(message.get('replace'), [])
        self.assertEquals(
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
        self.assertEquals(origin, 'openconfig')

    def test_get_prefix(self):
        """Test creating a prefix Path gNMI class."""
        path = xpath_util.get_prefix('rfc7951')
        self.assertIsInstance(path, proto.gnmi_pb2.Path)


if __name__ == '__main__':
    unittest.main()
