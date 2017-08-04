#!/bin/env python
""" Unit tests for the yang.ncdiff cisco-shared package. """

import unittest
from yang.ncdiff import *
from yang.connector import Netconf
from ats.topology import loader

def my_execute(*args, **kwargs):
    reply_xml = """<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="101"><data><network-instances xmlns="http://openconfig.net/yang/network-instance"><network-instance><name>Mgmt-intf</name><config><name>Mgmt-intf</name><type xmlns:oc-ni-types="http://openconfig.net/yang/network-instance-types">oc-ni-types:L3VRF</type><enabled-address-families xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</enabled-address-families><enabled-address-families xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</enabled-address-families></config><interfaces><interface><id>GigabitEthernet0</id><config><id>GigabitEthernet0</id><interface>GigabitEthernet0</interface></config></interface></interfaces><tables><table><protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol><address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family><config><protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol><address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family></config></table><table><protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol><address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family><config><protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol><address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family></config></table><table><protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol><address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family><config><protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol><address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family></config></table><table><protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol><address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family><config><protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol><address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family></config></table></tables><protocols><protocol><identifier xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</identifier><name>100</name><config><identifier xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</identifier><name>100</name></config><bgp><global><graceful-restart><config><enabled>false</enabled></config></graceful-restart><route-selection-options><config><always-compare-med>false</always-compare-med></config></route-selection-options></global></bgp></protocol><protocol><identifier xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</identifier><name>DEFAULT</name><config><identifier xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</identifier><name>DEFAULT</name></config><static-routes><static><prefix>0.0.0.0/0</prefix><config><prefix>0.0.0.0/0</prefix></config><next-hops><next-hop><index>5.28.0.1</index><config><index>5.28.0.1</index><next-hop>5.28.0.1</next-hop></config></next-hop></next-hops></static></static-routes></protocol><protocol><identifier xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</identifier><name>DEFAULT</name><config><identifier xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</identifier><name>DEFAULT</name></config></protocol></protocols></network-instance></network-instances></data></rpc-reply>"""
    reply = operations.rpc.RPCReply(reply_xml)
    reply.parse()
    return reply

Netconf.execute = my_execute


class MySSHSession():

    def __init__(self):
        self._is_stopped = False
        self._connected = False

    @property
    def connected(self):
        return self._connected

    def connect(self, host=None, port=None, username=None, password=None, hostkey_verify=None):
        self._connected = True

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


class TestNcDiff(unittest.TestCase):

    def setUp(self):
        self.yaml = \
            'devices:\n' \
            '    dummy:\n' \
            '        type: dummy_device\n' \
            '        connections:\n' \
            '            netconf:\n' \
            '                class: yang.ncdiff.ModelDevice\n' \
            '                ip : "1.2.3.4"\n' \
            '                port: 830\n' \
            '                username: admin\n' \
            '                password: admin\n'

        self.testbed = loader.load(self.yaml)
        self.device = self.testbed.devices['dummy']
        self.nc_device = ModelDevice(device=self.device,
                                     alias='nc', via='netconf')
        self.nc_device._session = MySSHSession()
        self.nc_device.connect()
        self.d = self.nc_device
        self.d.load_model('openconfig-interfaces@2016-12-22.xml')
        self.d.load_model('openconfig-network-instance@2017-01-13.xml')
        self.d.load_model('Cisco-IOS-XE-native@2017-03-24.xml')
        self.parser = etree.XMLParser(remove_blank_text=True)

    def test_delta_1(self):
        xml1 = """
            <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"
                       message-id="101">
              <data>
                <interfaces xmlns="http://openconfig.net/yang/interfaces">
                  <interface>
                    <name>GigabitEthernet1/0/1</name>
                    <config>
                      <type xmlns:ianaift="urn:ietf:params:xml:ns:yang:iana-if-type">ianaift:ethernetCsmacd</type>
                      <name>GigabitEthernet1/0/1</name>
                      <enabled>true</enabled>
                    </config>
                    <routed-vlan xmlns="http://openconfig.net/yang/vlan">
                      <ipv6 xmlns="http://openconfig.net/yang/interfaces/ip">
                        <config>
                          <enabled>false</enabled>
                        </config>
                      </ipv6>
                    </routed-vlan>
                  </interface>
                  <interface>
                    <name>GigabitEthernet1/0/10</name>
                    <config>
                      <type xmlns:ianaift="urn:ietf:params:xml:ns:yang:iana-if-type">ianaift:ethernetCsmacd</type>
                      <name>GigabitEthernet1/0/10</name>
                      <enabled>true</enabled>
                    </config>
                    <routed-vlan xmlns="http://openconfig.net/yang/vlan">
                      <ipv6 xmlns="http://openconfig.net/yang/interfaces/ip">
                        <config>
                          <enabled>false</enabled>
                        </config>
                      </ipv6>
                    </routed-vlan>
                  </interface>
                </interfaces>
              </data>
            </rpc-reply>
            """
        xml2 = """
            <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"
                       message-id="101">
              <data>
                <interfaces xmlns="http://openconfig.net/yang/interfaces">
                  <interface>
                    <name>GigabitEthernet1/0/1</name>
                    <config>
                      <type xmlns:ianaift="urn:ietf:params:xml:ns:yang:iana-if-type">ianaift:ethernetCsmacd</type>
                      <name>GigabitEthernet1/0/1</name>
                      <enabled>true</enabled>
                    </config>
                    <ethernet xmlns="http://openconfig.net/yang/interfaces/ethernet">
                      <config>
                        <port-speed>SPEED_10MB</port-speed>
                      </config>
                    </ethernet>
                    <routed-vlan xmlns="http://openconfig.net/yang/vlan">
                      <ipv6 xmlns="http://openconfig.net/yang/interfaces/ip">
                        <config>
                          <enabled>false</enabled>
                        </config>
                      </ipv6>
                    </routed-vlan>
                  </interface>
                  <interface>
                    <name>GigabitEthernet1/0/10</name>
                    <config>
                      <type xmlns:ianaift="urn:ietf:params:xml:ns:yang:iana-if-type">ianaift:ethernetCsmacd</type>
                      <name>GigabitEthernet1/0/10</name>
                      <enabled>true</enabled>
                    </config>
                    <routed-vlan xmlns="http://openconfig.net/yang/vlan">
                      <ipv6 xmlns="http://openconfig.net/yang/interfaces/ip">
                        <config>
                          <enabled>false</enabled>
                        </config>
                      </ipv6>
                    </routed-vlan>
                  </interface>
                </interfaces>
              </data>
            </rpc-reply>
            """
        delta1 = """
            <xc:config xmlns:xc="urn:ietf:params:xml:ns:netconf:base:1.0">
              <interfaces xmlns="http://openconfig.net/yang/interfaces">
                <interface>
                  <name>GigabitEthernet1/0/1</name>
                  <ethernet xmlns="http://openconfig.net/yang/interfaces/ethernet">
                    <config>
                      <port-speed>SPEED_10MB</port-speed>
                    </config>
                  </ethernet>
                </interface>
              </interfaces>
            </xc:config>
            """
        delta2 = """
            <xc:config xmlns:xc="urn:ietf:params:xml:ns:netconf:base:1.0">
              <interfaces xmlns="http://openconfig.net/yang/interfaces">
                <interface>
                  <name>GigabitEthernet1/0/1</name>
                  <ns0:ethernet xmlns:ns0="http://openconfig.net/yang/interfaces/ethernet"
                                xc:operation="delete"/>
                </interface>
              </interfaces>
            </xc:config>
            """
        config1 = NcConfig(self.d, xml1)
        config2 = NcConfig(self.d, xml2)
        delta = config2 - config1
        expected_delta = NcConfigDelta(self.d,
                                       etree.XML(delta1, self.parser),
                                       etree.XML(delta2, self.parser))
        self.assertEqual(delta, expected_delta)

    def test_delta_2(self):
        xml1 = """
            <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"
                       message-id="101">
              <data>
                <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
                  <router>
                    <bgp xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-bgp">
                      <id>10</id>
                      <bgp>
                        <router-id>10.8.55.30</router-id>
                        <log-neighbor-changes/>
                      </bgp>
                    </bgp>
                  </router>
                </native>
              </data>
            </rpc-reply>
            """
        xml2 = """
            <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"
                       message-id="101">
              <data>
                <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
                  <router>
                    <bgp xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-bgp">
                      <id>10</id>
                      <bgp>
                        <router-id>10.8.55.30</router-id>
                        <log-neighbor-changes/>
                        <listen>
                          <limit>2100</limit>
                          <range>
                            <network-range>10.44.0.0/16</network-range>
                            <peer-group>INET1-SPOKES</peer-group>
                          </range>
                        </listen>
                      </bgp>
                      <address-family>
                        <no-vrf>
                          <ipv4>
                            <af-name>unicast</af-name>
                          </ipv4>
                        </no-vrf>
                      </address-family>
                    </bgp>
                  </router>
                </native>
              </data>
            </rpc-reply>
            """
        delta1 = """
            <xc:config xmlns:xc="urn:ietf:params:xml:ns:netconf:base:1.0">
              <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
                <router>
                  <bgp xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-bgp">
                    <id>10</id>
                    <bgp>
                      <listen>
                        <limit>2100</limit>
                        <range>
                          <network-range>10.44.0.0/16</network-range>
                          <peer-group>INET1-SPOKES</peer-group>
                        </range>
                      </listen>
                    </bgp>
                    <address-family>
                      <no-vrf>
                        <ipv4>
                          <af-name>unicast</af-name>
                        </ipv4>
                      </no-vrf>
                    </address-family>
                  </bgp>
                </router>
              </native>
            </xc:config>
            """
        delta2 = """
            <xc:config xmlns:xc="urn:ietf:params:xml:ns:netconf:base:1.0">
              <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
                <router>
                  <bgp xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-bgp">
                    <id>10</id>
                    <bgp>
                      <listen xc:operation="delete"/>
                    </bgp>
                    <address-family xc:operation="delete"/>
                  </bgp>
                </router>
              </native>
            </xc:config>
            """
        config1 = NcConfig(self.d, xml1)
        config2 = NcConfig(self.d, xml2)
        delta = config2 - config1
        expected_delta = NcConfigDelta(self.d, delta1, delta2)
        self.assertEqual(delta, expected_delta)

    def test_delta_3(self):
        config_xml1 = """
            <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="101">
              <data>
                <network-instances xmlns="http://openconfig.net/yang/network-instance">
                  <network-instance>
                    <name>default</name>
                    <config>
                      <name>default</name>
                      <type xmlns:oc-ni-types="http://openconfig.net/yang/network-instance-types">oc-ni-types:DEFAULT_INSTANCE</type>
                      <description>default-vrf [read-only]</description>
                    </config>
                    <table-connections>
                      <table-connection>
                        <src-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</src-protocol>
                        <dst-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</dst-protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        <config>
                          <src-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</src-protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                          <dst-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</dst-protocol>
                          <import-policy>ROUTEMAP1</import-policy>
                          <import-policy>ROUTEMAP2</import-policy>
                          <default-import-policy>REJECT_ROUTE</default-import-policy>
                        </config>
                      </table-connection>
                    </table-connections>
                  </network-instance>
                </network-instances>
              </data>
            </rpc-reply>
            """
        config_xml2 = """
            <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="101">
              <data>
                <network-instances xmlns="http://openconfig.net/yang/network-instance">
                  <network-instance>
                    <name>default</name>
                    <config>
                      <name>default</name>
                      <type xmlns:oc-ni-types="http://openconfig.net/yang/network-instance-types">oc-ni-types:DEFAULT_INSTANCE</type>
                      <description>default-vrf [read-only]</description>
                    </config>
                    <table-connections>
                      <table-connection>
                        <src-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</src-protocol>
                        <dst-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</dst-protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        <config>
                          <src-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</src-protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                          <dst-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</dst-protocol>
                          <import-policy>ROUTEMAP1</import-policy>
                          <import-policy>ROUTEMAP3</import-policy>
                          <import-policy>ROUTEMAP0</import-policy>
                          <import-policy>ROUTEMAP2</import-policy>
                          <default-import-policy>REJECT_ROUTE</default-import-policy>
                        </config>
                      </table-connection>
                    </table-connections>
                  </network-instance>
                </network-instances>
              </data>
            </rpc-reply>
            """
        config1 = NcConfig(self.d, config_xml1)
        config2 = NcConfig(self.d, config_xml2)
        # modify schema node
        nodes = config1.xpath('.//oc-netinst:network-instance'
                              '/oc-netinst:table-connections'
                              '/oc-netinst:table-connection'
                              '/oc-netinst:config/oc-netinst:import-policy')
        node = nodes[0]
        schema_node = config1.get_schema_node(node)
        schema_node.set('ordered-by', 'user')
        delta1 = config2 - config1
        config3 = config1 + delta1
        self.assertEqual(config2, config3)
        self.assertTrue(config2 <= config3)
        self.assertTrue(config2 >= config3)
        delta2 = config1 - config2
        config4 = config2 + delta2
        self.assertEqual(config1, config4)

    def test_delta_4(self):
        config_xml1 = """
            <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="101">
              <data>
                <network-instances xmlns="http://openconfig.net/yang/network-instance">
                  <network-instance>
                    <name>default</name>
                    <config>
                      <name>default</name>
                      <type xmlns:oc-ni-types="http://openconfig.net/yang/network-instance-types">oc-ni-types:DEFAULT_INSTANCE</type>
                      <description>default-vrf [read-only]</description>
                    </config>
                    <tables>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        </config>
                      </table>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                        </config>
                      </table>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        </config>
                      </table>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                        </config>
                      </table>
                    </tables>
                  </network-instance>
                </network-instances>
              </data>
            </rpc-reply>
            """
        config_xml2 = """
            <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="101">
              <data>
                <network-instances xmlns="http://openconfig.net/yang/network-instance">
                  <network-instance>
                    <name>default</name>
                    <config>
                      <name>default</name>
                      <type xmlns:oc-ni-types="http://openconfig.net/yang/network-instance-types">oc-ni-types:DEFAULT_INSTANCE</type>
                      <description>default-vrf [read-only]</description>
                    </config>
                    <tables>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        </config>
                      </table>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                        </config>
                      </table>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        </config>
                      </table>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        </config>
                      </table>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                        </config>
                      </table>
                    </tables>
                  </network-instance>
                </network-instances>
              </data>
            </rpc-reply>
            """
        config1 = NcConfig(self.d, config_xml1)
        config2 = NcConfig(self.d, config_xml2)
        # modify schema node
        nodes = config1.xpath('.//oc-netinst:network-instance'
                              '/oc-netinst:tables/oc-netinst:table')
        node = nodes[0]
        schema_node = config1.get_schema_node(node)
        schema_node.set('ordered-by', 'user')
        delta1 = config2 - config1
        config3 = config1 + delta1
        self.assertEqual(config2, config3)
        self.assertTrue(config2 <= config3)
        self.assertTrue(config2 >= config3)
        delta2 = config1 - config2
        config4 = config2 + delta2
        self.assertEqual(config1, config4)

    def test_xpath_1(self):
        xml = """
            <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"
                       message-id="101">
              <data>
                <interfaces xmlns="http://openconfig.net/yang/interfaces">
                  <interface>
                    <name>GigabitEthernet1/0/1</name>
                    <config>
                      <type xmlns:ianaift="urn:ietf:params:xml:ns:yang:iana-if-type">ianaift:ethernetCsmacd</type>
                      <name>GigabitEthernet1/0/1</name>
                      <enabled>true</enabled>
                    </config>
                    <ethernet xmlns="http://openconfig.net/yang/interfaces/ethernet">
                      <config>
                        <port-speed>SPEED_10MB</port-speed>
                      </config>
                    </ethernet>
                    <routed-vlan xmlns="http://openconfig.net/yang/vlan">
                      <ipv6 xmlns="http://openconfig.net/yang/interfaces/ip">
                        <config>
                          <enabled>false</enabled>
                        </config>
                      </ipv6>
                    </routed-vlan>
                  </interface>
                  <interface>
                    <name>GigabitEthernet1/0/10</name>
                    <config>
                      <type xmlns:ianaift="urn:ietf:params:xml:ns:yang:iana-if-type">ianaift:ethernetCsmacd</type>
                      <name>GigabitEthernet1/0/10</name>
                      <enabled>true</enabled>
                    </config>
                    <routed-vlan xmlns="http://openconfig.net/yang/vlan">
                      <ipv6 xmlns="http://openconfig.net/yang/interfaces/ip">
                        <config>
                          <enabled>false</enabled>
                        </config>
                      </ipv6>
                    </routed-vlan>
                  </interface>
                </interfaces>
              </data>
            </rpc-reply>
            """
        config = NcConfig(self.d, xml)
        result = config.xpath('/nc:config/oc-if:interfaces/oc-if:interface'
                              '[oc-if:name="GigabitEthernet1/0/1"]'
                              '/oc-eth:ethernet/oc-eth:config'
                              '/oc-eth:port-speed/text()')
        self.assertEqual(result, ['SPEED_10MB'])

    def test_filter_1(self):
        xml1 = """
            <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"
                       message-id="101">
              <data>
                <interfaces xmlns="http://openconfig.net/yang/interfaces">
                  <interface>
                    <name>GigabitEthernet0/0/1</name>
                    <config>
                      <type xmlns:ianaift="urn:ietf:params:xml:ns:yang:iana-if-type">ianaift:ethernetCsmacd</type>
                      <name>GigabitEthernet0/0/1</name>
                      <enabled>true</enabled>
                    </config>
                    <ethernet xmlns="http://openconfig.net/yang/interfaces/ethernet">
                      <config>
                        <port-speed>SPEED_10MB</port-speed>
                      </config>
                    </ethernet>
                    <routed-vlan xmlns="http://openconfig.net/yang/vlan">
                      <ipv6 xmlns="http://openconfig.net/yang/interfaces/ip">
                        <config>
                          <enabled>false</enabled>
                        </config>
                      </ipv6>
                    </routed-vlan>
                  </interface>
                  <interface>
                    <name>GigabitEthernet1/0/10</name>
                    <config>
                      <type xmlns:ianaift="urn:ietf:params:xml:ns:yang:iana-if-type">ianaift:ethernetCsmacd</type>
                      <name>GigabitEthernet1/0/10</name>
                      <enabled>true</enabled>
                    </config>
                    <routed-vlan xmlns="http://openconfig.net/yang/vlan">
                      <ipv6 xmlns="http://openconfig.net/yang/interfaces/ip">
                        <config>
                          <enabled>false</enabled>
                        </config>
                      </ipv6>
                    </routed-vlan>
                  </interface>
                </interfaces>
              </data>
            </rpc-reply>
            """
        xml2 = """
            <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"
                       message-id="101">
              <data>
                <interfaces xmlns="http://openconfig.net/yang/interfaces">
                  <interface>
                    <name>GigabitEthernet1/0/10</name>
                    <config>
                      <type xmlns:ianaift="urn:ietf:params:xml:ns:yang:iana-if-type">ianaift:ethernetCsmacd</type>
                      <name>GigabitEthernet1/0/10</name>
                      <enabled>true</enabled>
                    </config>
                    <routed-vlan xmlns="http://openconfig.net/yang/vlan">
                      <ipv6 xmlns="http://openconfig.net/yang/interfaces/ip">
                        <config>
                          <enabled>false</enabled>
                        </config>
                      </ipv6>
                    </routed-vlan>
                  </interface>
                </interfaces>
              </data>
            </rpc-reply>
            """
        config1 = NcConfig(self.d, xml1)
        config2 = NcConfig(self.d, xml2)
        config3 = config1.filter('/nc:config/oc-if:interfaces/oc-if:interface'
                                 '[oc-if:name="GigabitEthernet1/0/10"]')
        self.assertEqual(config2, config3)

    def test_filter_2(self):
        xml1 = """
            <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"
                       message-id="101">
              <data>
                <interfaces xmlns="http://openconfig.net/yang/interfaces">
                  <interface>
                    <name>GigabitEthernet0/0/1</name>
                    <config>
                      <type xmlns:ianaift="urn:ietf:params:xml:ns:yang:iana-if-type">ianaift:ethernetCsmacd</type>
                      <name>GigabitEthernet0/0/1</name>
                      <enabled>true</enabled>
                    </config>
                    <ethernet xmlns="http://openconfig.net/yang/interfaces/ethernet">
                      <config>
                        <port-speed>SPEED_10MB</port-speed>
                      </config>
                    </ethernet>
                    <routed-vlan xmlns="http://openconfig.net/yang/vlan">
                      <ipv6 xmlns="http://openconfig.net/yang/interfaces/ip">
                        <config>
                          <enabled>false</enabled>
                        </config>
                      </ipv6>
                    </routed-vlan>
                  </interface>
                  <interface>
                    <name>GigabitEthernet1/0/10</name>
                    <config>
                      <type xmlns:ianaift="urn:ietf:params:xml:ns:yang:iana-if-type">ianaift:ethernetCsmacd</type>
                      <name>GigabitEthernet1/0/10</name>
                      <enabled>true</enabled>
                    </config>
                    <routed-vlan xmlns="http://openconfig.net/yang/vlan">
                      <ipv6 xmlns="http://openconfig.net/yang/interfaces/ip">
                        <config>
                          <enabled>false</enabled>
                        </config>
                      </ipv6>
                    </routed-vlan>
                  </interface>
                </interfaces>
              </data>
            </rpc-reply>
            """
        xml2 = """
            <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"
                       message-id="101">
              <data>
                <interfaces xmlns="http://openconfig.net/yang/interfaces">
                  <interface>
                    <name>GigabitEthernet1/0/10</name>
                    <config>
                      <type xmlns:ianaift="urn:ietf:params:xml:ns:yang:iana-if-type">ianaift:ethernetCsmacd</type>
                      <name>GigabitEthernet1/0/10</name>
                      <enabled>true</enabled>
                    </config>
                    <routed-vlan xmlns="http://openconfig.net/yang/vlan">
                      <ipv6 xmlns="http://openconfig.net/yang/interfaces/ip">
                        <config>
                          <enabled>false</enabled>
                        </config>
                      </ipv6>
                    </routed-vlan>
                  </interface>
                </interfaces>
              </data>
            </rpc-reply>
            """
        config1 = NcConfig(self.d, xml1)
        config2 = NcConfig(self.d, xml2)
        config3 = config1.filter('/nc:config/oc-if:interfaces/oc-if:interface'
                                 '[starts-with(oc-if:name/text(), '
                                 '"GigabitEthernet1")]')
        self.assertEqual(config2, config3)

    def test_add_1(self):
        config_xml1 = """
            <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="101">
              <data>
                <network-instances xmlns="http://openconfig.net/yang/network-instance">
                  <network-instance>
                    <name>default</name>
                    <config>
                      <name>default</name>
                      <type xmlns:oc-ni-types="http://openconfig.net/yang/network-instance-types">oc-ni-types:DEFAULT_INSTANCE</type>
                      <description>default-vrf [read-only]</description>
                    </config>
                    <tables>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        </config>
                      </table>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                        </config>
                      </table>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        </config>
                      </table>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                        </config>
                      </table>
                    </tables>
                  </network-instance>
                </network-instances>
              </data>
            </rpc-reply>
            """
        config_xml2 = """
            <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="101">
              <data>
                <network-instances xmlns="http://openconfig.net/yang/network-instance">
                  <network-instance>
                    <name>default</name>
                    <config>
                      <name>default</name>
                      <type xmlns:oc-ni-types="http://openconfig.net/yang/network-instance-types">oc-ni-types:DEFAULT_INSTANCE</type>
                      <description>default-vrf [read-only]</description>
                    </config>
                    <tables>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        </config>
                      </table>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        </config>
                      </table>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                        </config>
                      </table>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        </config>
                      </table>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                        </config>
                      </table>
                    </tables>
                  </network-instance>
                </network-instances>
              </data>
            </rpc-reply>
            """
        delta_xml1 = """
            <xc:config xmlns:xc="urn:ietf:params:xml:ns:netconf:base:1.0"
                       xmlns:yang="urn:ietf:params:xml:ns:yang:1">
              <network-instances xmlns="http://openconfig.net/yang/network-instance">
                <network-instance>
                  <name>default</name>
                  <config>
                    <name>default</name>
                    <type xmlns:oc-ni-types="http://openconfig.net/yang/network-instance-types">oc-ni-types:DEFAULT_INSTANCE</type>
                    <description>default-vrf [read-only]</description>
                  </config>
                  <tables>
                    <table yang:insert="first">
                      <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</protocol>
                      <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                      <config>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                      </config>
                    </table>
                  </tables>
                </network-instance>
              </network-instances>
            </xc:config>
            """
        delta_xml2 = """
            <xc:config xmlns:xc="urn:ietf:params:xml:ns:netconf:base:1.0"
                       xmlns:yang="urn:ietf:params:xml:ns:yang:1">
              <network-instances xmlns="http://openconfig.net/yang/network-instance">
                <network-instance>
                  <name>default</name>
                  <config>
                    <name>default</name>
                    <type xmlns:oc-ni-types="http://openconfig.net/yang/network-instance-types">oc-ni-types:DEFAULT_INSTANCE</type>
                    <description>default-vrf [read-only]</description>
                  </config>
                  <tables>
                    <table xc:operation="delete">
                      <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</protocol>
                      <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                    </table>
                  </tables>
                </network-instance>
              </network-instances>
            </xc:config>
            """
        config1 = NcConfig(self.d, config_xml1)
        config2 = NcConfig(self.d, config_xml2)
        delta = NcConfigDelta(self.d, delta_xml1, delta_xml2)
        # modify schema node
        nodes = config1.xpath('.//oc-netinst:network-instance'
                              '/oc-netinst:tables/oc-netinst:table')
        node = nodes[0]
        schema_node = config1.get_schema_node(node)
        schema_node.set('ordered-by', 'user')
        config3 = config1 + delta
        self.assertEqual(config2, config3)

    def test_add_2(self):
        config_xml1 = """
            <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="101">
              <data>
                <network-instances xmlns="http://openconfig.net/yang/network-instance">
                  <network-instance>
                    <name>default</name>
                    <config>
                      <name>default</name>
                      <type xmlns:oc-ni-types="http://openconfig.net/yang/network-instance-types">oc-ni-types:DEFAULT_INSTANCE</type>
                      <description>default-vrf [read-only]</description>
                    </config>
                    <tables>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        </config>
                      </table>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                        </config>
                      </table>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        </config>
                      </table>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                        </config>
                      </table>
                    </tables>
                  </network-instance>
                </network-instances>
              </data>
            </rpc-reply>
            """
        config_xml2 = """
            <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="101">
              <data>
                <network-instances xmlns="http://openconfig.net/yang/network-instance">
                  <network-instance>
                    <name>default</name>
                    <config>
                      <name>default</name>
                      <type xmlns:oc-ni-types="http://openconfig.net/yang/network-instance-types">oc-ni-types:DEFAULT_INSTANCE</type>
                      <description>default-vrf [read-only]</description>
                    </config>
                    <tables>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        </config>
                      </table>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                        </config>
                      </table>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        </config>
                      </table>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                        </config>
                      </table>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        </config>
                      </table>
                    </tables>
                  </network-instance>
                </network-instances>
              </data>
            </rpc-reply>
            """
        delta_xml1 = """
            <xc:config xmlns:xc="urn:ietf:params:xml:ns:netconf:base:1.0"
                       xmlns:yang="urn:ietf:params:xml:ns:yang:1">
              <network-instances xmlns="http://openconfig.net/yang/network-instance">
                <network-instance>
                  <name>default</name>
                  <config>
                    <name>default</name>
                    <type xmlns:oc-ni-types="http://openconfig.net/yang/network-instance-types">oc-ni-types:DEFAULT_INSTANCE</type>
                    <description>default-vrf [read-only]</description>
                  </config>
                  <tables>
                    <table yang:insert="last">
                      <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</protocol>
                      <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                      <config>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                      </config>
                    </table>
                  </tables>
                </network-instance>
              </network-instances>
            </xc:config>
            """
        delta_xml2 = """
            <xc:config xmlns:xc="urn:ietf:params:xml:ns:netconf:base:1.0"
                       xmlns:yang="urn:ietf:params:xml:ns:yang:1">
              <network-instances xmlns="http://openconfig.net/yang/network-instance">
                <network-instance>
                  <name>default</name>
                  <config>
                    <name>default</name>
                    <type xmlns:oc-ni-types="http://openconfig.net/yang/network-instance-types">oc-ni-types:DEFAULT_INSTANCE</type>
                    <description>default-vrf [read-only]</description>
                  </config>
                  <tables>
                    <table xc:operation="delete">
                      <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</protocol>
                      <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                    </table>
                  </tables>
                </network-instance>
              </network-instances>
            </xc:config>
            """
        config1 = NcConfig(self.d, config_xml1)
        config2 = NcConfig(self.d, config_xml2)
        delta = NcConfigDelta(self.d, delta_xml1, delta_xml2)
        # modify schema node
        nodes = config1.xpath('.//oc-netinst:network-instance'
                              '/oc-netinst:tables/oc-netinst:table')
        node = nodes[0]
        schema_node = config1.get_schema_node(node)
        schema_node.set('ordered-by', 'user')
        config3 = config1 + delta
        self.assertEqual(config2, config3)

    def test_add_3(self):
        config_xml1 = """
            <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="101">
              <data>
                <network-instances xmlns="http://openconfig.net/yang/network-instance">
                  <network-instance>
                    <name>default</name>
                    <config>
                      <name>default</name>
                      <type xmlns:oc-ni-types="http://openconfig.net/yang/network-instance-types">oc-ni-types:DEFAULT_INSTANCE</type>
                      <description>default-vrf [read-only]</description>
                    </config>
                    <tables>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        </config>
                      </table>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                        </config>
                      </table>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        </config>
                      </table>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                        </config>
                      </table>
                    </tables>
                  </network-instance>
                </network-instances>
              </data>
            </rpc-reply>
            """
        config_xml2 = """
            <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="101">
              <data>
                <network-instances xmlns="http://openconfig.net/yang/network-instance">
                  <network-instance>
                    <name>default</name>
                    <config>
                      <name>default</name>
                      <type xmlns:oc-ni-types="http://openconfig.net/yang/network-instance-types">oc-ni-types:DEFAULT_INSTANCE</type>
                      <description>default-vrf [read-only]</description>
                    </config>
                    <tables>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        </config>
                      </table>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                        </config>
                      </table>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        </config>
                      </table>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        </config>
                      </table>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                        </config>
                      </table>
                    </tables>
                  </network-instance>
                </network-instances>
              </data>
            </rpc-reply>
            """
        delta_xml1 = """
            <xc:config xmlns:xc="urn:ietf:params:xml:ns:netconf:base:1.0"
                       xmlns:yang="urn:ietf:params:xml:ns:yang:1">
              <network-instances xmlns="http://openconfig.net/yang/network-instance">
                <network-instance>
                  <name>default</name>
                  <config>
                    <name>default</name>
                    <type xmlns:oc-ni-types="http://openconfig.net/yang/network-instance-types">oc-ni-types:DEFAULT_INSTANCE</type>
                    <description>default-vrf [read-only]</description>
                  </config>
                  <tables>
                    <table xmlns:oc-pol-types="http://openconfig.net/yang/policy-types"
                           xmlns:oc-types="http://openconfig.net/yang/openconfig-types"
                           xc:operation="create"
                           yang:insert="after"
                           yang:key="[protocol='oc-pol-types:STATIC'][address-family='oc-types:IPV4']">
                      <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</protocol>
                      <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                      <config>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                      </config>
                    </table>
                    <table xc:operation="replace"
                           yang:insert="after"
                           yang:key="[protocol='oc-pol-types:DIRECTLY_CONNECTED'][address-family='oc-types:IPV4']">
                      <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                      <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                      <config>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                      </config>
                    </table>
                  </tables>
                </network-instance>
              </network-instances>
            </xc:config>
            """
        delta_xml2 = """
            <xc:config xmlns:xc="urn:ietf:params:xml:ns:netconf:base:1.0"
                       xmlns:yang="urn:ietf:params:xml:ns:yang:1">
              <network-instances xmlns="http://openconfig.net/yang/network-instance">
                <network-instance>
                  <name>default</name>
                  <config>
                    <name>default</name>
                    <type xmlns:oc-ni-types="http://openconfig.net/yang/network-instance-types">oc-ni-types:DEFAULT_INSTANCE</type>
                    <description>default-vrf [read-only]</description>
                  </config>
                  <tables>
                    <table xc:operation="delete">
                      <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</protocol>
                      <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                    </table>
                  </tables>
                </network-instance>
              </network-instances>
            </xc:config>
            """
        config1 = NcConfig(self.d, config_xml1)
        config2 = NcConfig(self.d, config_xml2)
        delta = NcConfigDelta(self.d, delta_xml1, delta_xml2)
        # modify schema node
        nodes = config1.xpath('.//oc-netinst:network-instance'
                              '/oc-netinst:tables/oc-netinst:table')
        node = nodes[0]
        schema_node = config1.get_schema_node(node)
        schema_node.set('ordered-by', 'user')
        config3 = config1 + delta
        self.assertEqual(config2, config3)
        config4 = config3 - delta
        self.assertEqual(config1, config4)

    def test_add_4(self):
        config_xml1 = """
            <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="101">
              <data>
                <network-instances xmlns="http://openconfig.net/yang/network-instance">
                  <network-instance>
                    <name>default</name>
                    <config>
                      <name>default</name>
                      <type xmlns:oc-ni-types="http://openconfig.net/yang/network-instance-types">oc-ni-types:DEFAULT_INSTANCE</type>
                      <description>default-vrf [read-only]</description>
                    </config>
                    <tables>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        </config>
                      </table>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                        </config>
                      </table>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        </config>
                      </table>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                        </config>
                      </table>
                    </tables>
                  </network-instance>
                </network-instances>
              </data>
            </rpc-reply>
            """
        config_xml2 = """
            <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="101">
              <data>
                <network-instances xmlns="http://openconfig.net/yang/network-instance">
                  <network-instance>
                    <name>default</name>
                    <config>
                      <name>default</name>
                      <type xmlns:oc-ni-types="http://openconfig.net/yang/network-instance-types">oc-ni-types:DEFAULT_INSTANCE</type>
                      <description>default-vrf [read-only]</description>
                    </config>
                    <tables>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        </config>
                      </table>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                        </config>
                      </table>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        </config>
                      </table>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        </config>
                      </table>
                      <table>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                        <config>
                          <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:STATIC</protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV6</address-family>
                        </config>
                      </table>
                    </tables>
                  </network-instance>
                </network-instances>
              </data>
            </rpc-reply>
            """
        delta_xml1 = """
            <xc:config xmlns:xc="urn:ietf:params:xml:ns:netconf:base:1.0"
                       xmlns:yang="urn:ietf:params:xml:ns:yang:1">
              <network-instances xmlns="http://openconfig.net/yang/network-instance">
                <network-instance>
                  <name>default</name>
                  <config>
                    <name>default</name>
                    <type xmlns:oc-ni-types="http://openconfig.net/yang/network-instance-types">oc-ni-types:DEFAULT_INSTANCE</type>
                    <description>default-vrf [read-only]</description>
                  </config>
                  <tables>
                    <table xmlns:oc-pol-types="http://openconfig.net/yang/policy-types"
                           xmlns:oc-types="http://openconfig.net/yang/openconfig-types"
                           yang:insert="before"
                           yang:key="[protocol='oc-pol-types:STATIC'][address-family='oc-types:IPV4']">
                      <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</protocol>
                      <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                      <config>
                        <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                      </config>
                    </table>
                  </tables>
                </network-instance>
              </network-instances>
            </xc:config>
            """
        delta_xml2 = """
            <xc:config xmlns:xc="urn:ietf:params:xml:ns:netconf:base:1.0"
                       xmlns:yang="urn:ietf:params:xml:ns:yang:1">
              <network-instances xmlns="http://openconfig.net/yang/network-instance">
                <network-instance>
                  <name>default</name>
                  <config>
                    <name>default</name>
                    <type xmlns:oc-ni-types="http://openconfig.net/yang/network-instance-types">oc-ni-types:DEFAULT_INSTANCE</type>
                    <description>default-vrf [read-only]</description>
                  </config>
                  <tables>
                    <table xc:operation="delete">
                      <protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</protocol>
                      <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                    </table>
                  </tables>
                </network-instance>
              </network-instances>
            </xc:config>
            """
        config1 = NcConfig(self.d, config_xml1)
        config2 = NcConfig(self.d, config_xml2)
        delta = NcConfigDelta(self.d, delta_xml1, delta_xml2)
        # modify schema node
        nodes = config1.xpath('.//oc-netinst:network-instance'
                              '/oc-netinst:tables/oc-netinst:table')
        node = nodes[0]
        schema_node = config1.get_schema_node(node)
        schema_node.set('ordered-by', 'user')
        config3 = config1 + delta
        self.assertEqual(config2, config3)

    def test_add_5(self):
        config_xml1 = """
            <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="101">
              <data>
                <network-instances xmlns="http://openconfig.net/yang/network-instance">
                  <network-instance>
                    <name>default</name>
                    <config>
                      <name>default</name>
                      <type xmlns:oc-ni-types="http://openconfig.net/yang/network-instance-types">oc-ni-types:DEFAULT_INSTANCE</type>
                      <description>default-vrf [read-only]</description>
                    </config>
                    <table-connections>
                      <table-connection>
                        <src-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</src-protocol>
                        <dst-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</dst-protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        <config>
                          <src-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</src-protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                          <dst-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</dst-protocol>
                          <import-policy>ROUTEMAP1</import-policy>
                          <import-policy>ROUTEMAP2</import-policy>
                          <default-import-policy>REJECT_ROUTE</default-import-policy>
                        </config>
                      </table-connection>
                    </table-connections>
                  </network-instance>
                </network-instances>
              </data>
            </rpc-reply>
            """
        config_xml2 = """
            <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="101">
              <data>
                <network-instances xmlns="http://openconfig.net/yang/network-instance">
                  <network-instance>
                    <name>default</name>
                    <config>
                      <name>default</name>
                      <type xmlns:oc-ni-types="http://openconfig.net/yang/network-instance-types">oc-ni-types:DEFAULT_INSTANCE</type>
                      <description>default-vrf [read-only]</description>
                    </config>
                    <table-connections>
                      <table-connection>
                        <src-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</src-protocol>
                        <dst-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</dst-protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        <config>
                          <src-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</src-protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                          <dst-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</dst-protocol>
                          <import-policy>ROUTEMAP0</import-policy>
                          <import-policy>ROUTEMAP1</import-policy>
                          <import-policy>ROUTEMAP2</import-policy>
                          <import-policy>ROUTEMAP3</import-policy>
                          <default-import-policy>REJECT_ROUTE</default-import-policy>
                        </config>
                      </table-connection>
                    </table-connections>
                  </network-instance>
                </network-instances>
              </data>
            </rpc-reply>
            """
        delta_xml1 = """
            <xc:config xmlns:xc="urn:ietf:params:xml:ns:netconf:base:1.0"
                       xmlns:yang="urn:ietf:params:xml:ns:yang:1">
              <network-instances xmlns="http://openconfig.net/yang/network-instance">
                <network-instance>
                  <name>default</name>
                  <table-connections>
                    <table-connection>
                      <src-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</src-protocol>
                      <dst-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</dst-protocol>
                      <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                      <config>
                        <import-policy yang:insert="first">ROUTEMAP0</import-policy>
                        <import-policy yang:insert="last">ROUTEMAP3</import-policy>
                      </config>
                    </table-connection>
                  </table-connections>
                </network-instance>
              </network-instances>
            </xc:config>
            """
        delta_xml2 = """
            <xc:config xmlns:xc="urn:ietf:params:xml:ns:netconf:base:1.0"
                       xmlns:yang="urn:ietf:params:xml:ns:yang:1">
              <network-instances xmlns="http://openconfig.net/yang/network-instance">
                <network-instance>
                  <name>default</name>
                  <table-connections>
                    <table-connection>
                      <src-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</src-protocol>
                      <dst-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</dst-protocol>
                      <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                      <config>
                        <import-policy xc:operation="delete">ROUTEMAP0</import-policy>
                        <import-policy xc:operation="delete">ROUTEMAP3</import-policy>
                      </config>
                    </table-connection>
                  </table-connections>
                </network-instance>
              </network-instances>
            </xc:config>
            """
        config1 = NcConfig(self.d, config_xml1)
        config2 = NcConfig(self.d, config_xml2)
        delta = NcConfigDelta(self.d, delta_xml1, delta_xml2)
        # modify schema node
        nodes = config1.xpath('.//oc-netinst:network-instance'
                              '/oc-netinst:table-connections'
                              '/oc-netinst:table-connection'
                              '/oc-netinst:config/oc-netinst:import-policy')
        node = nodes[0]
        schema_node = config1.get_schema_node(node)
        schema_node.set('ordered-by', 'user')
        config3 = config1 + delta
        self.assertEqual(config2, config3)

    def test_add_6(self):
        config_xml1 = """
            <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="101">
              <data>
                <network-instances xmlns="http://openconfig.net/yang/network-instance">
                  <network-instance>
                    <name>default</name>
                    <config>
                      <name>default</name>
                      <type xmlns:oc-ni-types="http://openconfig.net/yang/network-instance-types">oc-ni-types:DEFAULT_INSTANCE</type>
                      <description>default-vrf [read-only]</description>
                    </config>
                    <table-connections>
                      <table-connection>
                        <src-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</src-protocol>
                        <dst-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</dst-protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        <config>
                          <src-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</src-protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                          <dst-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</dst-protocol>
                          <import-policy>ROUTEMAP1</import-policy>
                          <import-policy>ROUTEMAP2</import-policy>
                          <default-import-policy>REJECT_ROUTE</default-import-policy>
                        </config>
                      </table-connection>
                    </table-connections>
                  </network-instance>
                </network-instances>
              </data>
            </rpc-reply>
            """
        config_xml2 = """
            <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="101">
              <data>
                <network-instances xmlns="http://openconfig.net/yang/network-instance">
                  <network-instance>
                    <name>default</name>
                    <config>
                      <name>default</name>
                      <type xmlns:oc-ni-types="http://openconfig.net/yang/network-instance-types">oc-ni-types:DEFAULT_INSTANCE</type>
                      <description>default-vrf [read-only]</description>
                    </config>
                    <table-connections>
                      <table-connection>
                        <src-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</src-protocol>
                        <dst-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</dst-protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        <config>
                          <src-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</src-protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                          <dst-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</dst-protocol>
                          <import-policy>ROUTEMAP1</import-policy>
                          <import-policy>ROUTEMAP3</import-policy>
                          <import-policy>ROUTEMAP0</import-policy>
                          <import-policy>ROUTEMAP2</import-policy>
                          <default-import-policy>REJECT_ROUTE</default-import-policy>
                        </config>
                      </table-connection>
                    </table-connections>
                  </network-instance>
                </network-instances>
              </data>
            </rpc-reply>
            """
        delta_xml1 = """
            <xc:config xmlns:xc="urn:ietf:params:xml:ns:netconf:base:1.0"
                       xmlns:yang="urn:ietf:params:xml:ns:yang:1">
              <network-instances xmlns="http://openconfig.net/yang/network-instance">
                <network-instance>
                  <name>default</name>
                  <table-connections>
                    <table-connection>
                      <src-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</src-protocol>
                      <dst-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</dst-protocol>
                      <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                      <config>
                        <import-policy xc:operation="create"
                                       yang:insert="before"
                                       yang:value="ROUTEMAP2">ROUTEMAP0</import-policy>
                        <import-policy xc:operation="merge"
                                       yang:insert="after"
                                       yang:value="ROUTEMAP1">ROUTEMAP3</import-policy>
                      </config>
                    </table-connection>
                  </table-connections>
                </network-instance>
              </network-instances>
            </xc:config>
            """
        delta_xml2 = """
            <xc:config xmlns:xc="urn:ietf:params:xml:ns:netconf:base:1.0"
                       xmlns:yang="urn:ietf:params:xml:ns:yang:1">
              <network-instances xmlns="http://openconfig.net/yang/network-instance">
                <network-instance>
                  <name>default</name>
                  <table-connections>
                    <table-connection>
                      <src-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</src-protocol>
                      <dst-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</dst-protocol>
                      <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                      <config>
                        <import-policy xc:operation="delete">ROUTEMAP0</import-policy>
                        <import-policy xc:operation="delete">ROUTEMAP3</import-policy>
                      </config>
                    </table-connection>
                  </table-connections>
                </network-instance>
              </network-instances>
            </xc:config>
            """
        config1 = NcConfig(self.d, config_xml1)
        config2 = NcConfig(self.d, config_xml2)
        delta = NcConfigDelta(self.d, delta_xml1, delta_xml2)
        # modify schema node
        nodes = config1.xpath('.//oc-netinst:network-instance'
                              '/oc-netinst:table-connections'
                              '/oc-netinst:table-connection'
                              '/oc-netinst:config/oc-netinst:import-policy')
        node = nodes[0]
        schema_node = config1.get_schema_node(node)
        schema_node.set('ordered-by', 'user')
        config3 = config1 + delta
        self.assertEqual(config2, config3)
        config4 = config3 - delta
        self.assertEqual(config1, config4)

    def test_add_7(self):
        config_xml1 = """
            <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="101">
              <data>
                <network-instances xmlns="http://openconfig.net/yang/network-instance">
                  <network-instance>
                    <name>default</name>
                    <config>
                      <name>default</name>
                      <type xmlns:oc-ni-types="http://openconfig.net/yang/network-instance-types">oc-ni-types:DEFAULT_INSTANCE</type>
                      <description>default-vrf [read-only]</description>
                    </config>
                    <table-connections>
                      <table-connection>
                        <src-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</src-protocol>
                        <dst-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</dst-protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        <config>
                          <src-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</src-protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                          <dst-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</dst-protocol>
                          <import-policy>ROUTEMAP1</import-policy>
                          <import-policy>ROUTEMAP2</import-policy>
                          <default-import-policy>REJECT_ROUTE</default-import-policy>
                        </config>
                      </table-connection>
                    </table-connections>
                  </network-instance>
                </network-instances>
              </data>
            </rpc-reply>
            """
        config_xml2 = """
            <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"
                       message-id="101">
              <data>
                <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
                  <router>
                    <bgp xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-bgp">
                      <id>10</id>
                      <bgp>
                        <router-id>10.8.55.30</router-id>
                        <log-neighbor-changes/>
                      </bgp>
                    </bgp>
                  </router>
                </native>
              </data>
            </rpc-reply>
            """
        config_xml3 = """
            <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="101">
              <data>
                <network-instances xmlns="http://openconfig.net/yang/network-instance">
                  <network-instance>
                    <name>default</name>
                    <config>
                      <name>default</name>
                      <type xmlns:oc-ni-types="http://openconfig.net/yang/network-instance-types">oc-ni-types:DEFAULT_INSTANCE</type>
                      <description>default-vrf [read-only]</description>
                    </config>
                    <table-connections>
                      <table-connection>
                        <src-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</src-protocol>
                        <dst-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</dst-protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        <config>
                          <src-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</src-protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                          <dst-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</dst-protocol>
                          <import-policy>ROUTEMAP1</import-policy>
                          <import-policy>ROUTEMAP2</import-policy>
                          <default-import-policy>REJECT_ROUTE</default-import-policy>
                        </config>
                      </table-connection>
                    </table-connections>
                  </network-instance>
                </network-instances>
                <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
                  <router>
                    <bgp xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-bgp">
                      <id>10</id>
                      <bgp>
                        <router-id>10.8.55.30</router-id>
                        <log-neighbor-changes/>
                      </bgp>
                    </bgp>
                  </router>
                </native>
              </data>
            </rpc-reply>
            """
        config1 = NcConfig(self.d, config_xml1)
        config2 = NcConfig(self.d, config_xml2)
        config3 = NcConfig(self.d, config_xml3)
        config4 = config1 + config2
        self.assertEqual(config4, config3)

    def test_add_8(self):
        config_xml1 = """
            <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"
                       message-id="101">
              <data>
                <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
                  <router>
                    <bgp xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-bgp">
                      <id>10</id>
                      <bgp>
                        <router-id>10.8.55.30</router-id>
                      </bgp>
                    </bgp>
                  </router>
                </native>
              </data>
            </rpc-reply>
            """
        config_xml2 = """
            <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"
                       message-id="101">
              <data>
                <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
                  <router>
                    <bgp xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-bgp">
                      <id>10</id>
                      <bgp>
                        <router-id>10.8.55.30</router-id>
                        <log-neighbor-changes/>
                      </bgp>
                      <address-family>
                        <no-vrf>
                          <ipv4>
                            <af-name>unicast</af-name>
                          </ipv4>
                        </no-vrf>
                      </address-family>
                    </bgp>
                  </router>
                </native>
              </data>
            </rpc-reply>
            """
        config1 = NcConfig(self.d, config_xml1)
        config2 = NcConfig(self.d, config_xml2)
        config3 = config1 + config2
        self.assertEqual(config2, config3)

    def test_add_9(self):
        config_xml1 = """
            <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="101">
              <data>
                <network-instances xmlns="http://openconfig.net/yang/network-instance">
                  <network-instance>
                    <name>default</name>
                    <config>
                      <name>default</name>
                      <type xmlns:oc-ni-types="http://openconfig.net/yang/network-instance-types">oc-ni-types:DEFAULT_INSTANCE</type>
                      <description>default-vrf [read-only]</description>
                    </config>
                    <table-connections>
                      <table-connection>
                        <src-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</src-protocol>
                        <dst-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</dst-protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        <config>
                          <src-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</src-protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                          <dst-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</dst-protocol>
                          <import-policy>ROUTEMAP1</import-policy>
                          <import-policy>ROUTEMAP2</import-policy>
                          <default-import-policy>REJECT_ROUTE</default-import-policy>
                        </config>
                      </table-connection>
                    </table-connections>
                  </network-instance>
                </network-instances>
              </data>
            </rpc-reply>
            """
        delta_xml1 = """
            <xc:config xmlns:xc="urn:ietf:params:xml:ns:netconf:base:1.0"
                       xmlns:yang="urn:ietf:params:xml:ns:yang:1">
              <network-instances xmlns="http://openconfig.net/yang/network-instance">
                <network-instance>
                  <name>default</name>
                  <table-connections>
                    <table-connection>
                      <src-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</src-protocol>
                      <dst-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</dst-protocol>
                      <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                      <config>
                        <import-policy xc:operation="create"
                                       yang:insert="before"
                                       yang:value="ROUTEMAP2">ROUTEMAP1</import-policy>
                      </config>
                    </table-connection>
                  </table-connections>
                </network-instance>
              </network-instances>
            </xc:config>
            """
        delta_xml2 = """
            <xc:config xmlns:xc="urn:ietf:params:xml:ns:netconf:base:1.0"
                       xmlns:yang="urn:ietf:params:xml:ns:yang:1">
              <network-instances xmlns="http://openconfig.net/yang/network-instance">
                <network-instance>
                  <name>default</name>
                  <table-connections>
                    <table-connection>
                      <src-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</src-protocol>
                      <dst-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</dst-protocol>
                      <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                      <config>
                        <import-policy xc:operation="delete">ROUTEMAP0</import-policy>
                        <import-policy xc:operation="delete">ROUTEMAP3</import-policy>
                      </config>
                    </table-connection>
                  </table-connections>
                </network-instance>
              </network-instances>
            </xc:config>
            """
        config1 = NcConfig(self.d, config_xml1)
        delta = NcConfigDelta(self.d, delta_xml1, delta_xml2)
        # modify schema node
        nodes = config1.xpath('.//oc-netinst:network-instance'
                              '/oc-netinst:table-connections'
                              '/oc-netinst:table-connection'
                              '/oc-netinst:config/oc-netinst:import-policy')
        node = nodes[0]
        schema_node = config1.get_schema_node(node)
        schema_node.set('ordered-by', 'user')
        self.assertRaises(ConfigDeltaError,
                          config1.__add__,
                          delta)

    def test_add_10(self):
        config_xml1 = """
            <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="101">
              <data>
                <network-instances xmlns="http://openconfig.net/yang/network-instance">
                  <network-instance>
                    <name>default</name>
                    <config>
                      <name>default</name>
                      <type xmlns:oc-ni-types="http://openconfig.net/yang/network-instance-types">oc-ni-types:DEFAULT_INSTANCE</type>
                      <description>default-vrf [read-only]</description>
                    </config>
                    <table-connections>
                      <table-connection>
                        <src-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</src-protocol>
                        <dst-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</dst-protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        <config>
                          <src-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</src-protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                          <dst-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</dst-protocol>
                          <import-policy>ROUTEMAP1</import-policy>
                          <import-policy>ROUTEMAP2</import-policy>
                          <default-import-policy>REJECT_ROUTE</default-import-policy>
                        </config>
                      </table-connection>
                    </table-connections>
                  </network-instance>
                </network-instances>
              </data>
            </rpc-reply>
            """
        delta_xml1 = """
            <xc:config xmlns:xc="urn:ietf:params:xml:ns:netconf:base:1.0"
                       xmlns:yang="urn:ietf:params:xml:ns:yang:1">
              <network-instances xmlns="http://openconfig.net/yang/network-instance">
                <network-instance>
                  <name>default</name>
                  <table-connections>
                    <table-connection>
                      <src-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</src-protocol>
                      <dst-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</dst-protocol>
                      <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                      <config>
                        <import-policy yang:insert="before"
                                       yang:value="ROUTEMAP7">ROUTEMAP1</import-policy>
                      </config>
                    </table-connection>
                  </table-connections>
                </network-instance>
              </network-instances>
            </xc:config>
            """
        delta_xml2 = """
            <xc:config xmlns:xc="urn:ietf:params:xml:ns:netconf:base:1.0"
                       xmlns:yang="urn:ietf:params:xml:ns:yang:1">
              <network-instances xmlns="http://openconfig.net/yang/network-instance">
                <network-instance>
                  <name>default</name>
                  <table-connections>
                    <table-connection>
                      <src-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</src-protocol>
                      <dst-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</dst-protocol>
                      <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                      <config>
                        <import-policy xc:operation="delete">ROUTEMAP0</import-policy>
                        <import-policy xc:operation="delete">ROUTEMAP3</import-policy>
                      </config>
                    </table-connection>
                  </table-connections>
                </network-instance>
              </network-instances>
            </xc:config>
            """
        config1 = NcConfig(self.d, config_xml1)
        delta = NcConfigDelta(self.d, delta_xml1, delta_xml2)
        # modify schema node
        nodes = config1.xpath('.//oc-netinst:network-instance'
                              '/oc-netinst:table-connections'
                              '/oc-netinst:table-connection'
                              '/oc-netinst:config/oc-netinst:import-policy')
        node = nodes[0]
        schema_node = config1.get_schema_node(node)
        schema_node.set('ordered-by', 'user')
        self.assertRaises(ConfigDeltaError,
                          config1.__add__,
                          delta)

    def test_add_11(self):
        config_xml1 = """
            <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="101">
              <data>
                <network-instances xmlns="http://openconfig.net/yang/network-instance">
                  <network-instance>
                    <name>default</name>
                    <config>
                      <name>default</name>
                      <type xmlns:oc-ni-types="http://openconfig.net/yang/network-instance-types">oc-ni-types:DEFAULT_INSTANCE</type>
                      <description>default-vrf [read-only]</description>
                    </config>
                    <table-connections>
                      <table-connection>
                        <src-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</src-protocol>
                        <dst-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</dst-protocol>
                        <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                        <config>
                          <src-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</src-protocol>
                          <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                          <dst-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</dst-protocol>
                          <import-policy>ROUTEMAP1</import-policy>
                          <import-policy>ROUTEMAP2</import-policy>
                          <default-import-policy>REJECT_ROUTE</default-import-policy>
                        </config>
                      </table-connection>
                    </table-connections>
                  </network-instance>
                </network-instances>
              </data>
            </rpc-reply>
            """
        delta_xml1 = """
            <xc:config xmlns:xc="urn:ietf:params:xml:ns:netconf:base:1.0"
                       xmlns:yang="urn:ietf:params:xml:ns:yang:1">
              <network-instances xmlns="http://openconfig.net/yang/network-instance">
                <network-instance>
                  <name>default</name>
                  <table-connections>
                    <table-connection>
                      <src-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</src-protocol>
                      <dst-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</dst-protocol>
                      <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                      <config>
                        <import-policy yang:insert="after">ROUTEMAP1</import-policy>
                      </config>
                    </table-connection>
                  </table-connections>
                </network-instance>
              </network-instances>
            </xc:config>
            """
        delta_xml2 = """
            <xc:config xmlns:xc="urn:ietf:params:xml:ns:netconf:base:1.0"
                       xmlns:yang="urn:ietf:params:xml:ns:yang:1">
              <network-instances xmlns="http://openconfig.net/yang/network-instance">
                <network-instance>
                  <name>default</name>
                  <table-connections>
                    <table-connection>
                      <src-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:DIRECTLY_CONNECTED</src-protocol>
                      <dst-protocol xmlns:oc-pol-types="http://openconfig.net/yang/policy-types">oc-pol-types:BGP</dst-protocol>
                      <address-family xmlns:oc-types="http://openconfig.net/yang/openconfig-types">oc-types:IPV4</address-family>
                      <config>
                        <import-policy xc:operation="delete">ROUTEMAP0</import-policy>
                        <import-policy xc:operation="delete">ROUTEMAP3</import-policy>
                      </config>
                    </table-connection>
                  </table-connections>
                </network-instance>
              </network-instances>
            </xc:config>
            """
        config1 = NcConfig(self.d, config_xml1)
        delta = NcConfigDelta(self.d, delta_xml1, delta_xml2)
        # modify schema node
        nodes = config1.xpath('.//oc-netinst:network-instance'
                              '/oc-netinst:table-connections'
                              '/oc-netinst:table-connection'
                              '/oc-netinst:config/oc-netinst:import-policy')
        node = nodes[0]
        schema_node = config1.get_schema_node(node)
        schema_node.set('ordered-by', 'user')
        self.assertRaises(ConfigDeltaError,
                          config1.__add__,
                          delta)

    def test_get_node_1(self):
        path = [
            '{http://cisco.com/ns/yang/Cisco-IOS-XE-native}native',
            '{http://cisco.com/ns/yang/Cisco-IOS-XE-native}interface',
            '{http://cisco.com/ns/yang/Cisco-IOS-XE-native}GigabitEthernet',
            '{http://cisco.com/ns/yang/Cisco-IOS-XE-native}keepalive',
            ]
        schema_node = self.d.get_node(path)
        assert schema_node is not None

    def test_get_prefix_1(self):
        prefix = self.d.get_prefix('urn:ietf:params:xml:ns:yang:iana-if-type')
        self.assertEqual(prefix, 'ianaift')

    def test_get_config_1(self):
        expected_ns = {
            'ns00': 'urn:ietf:params:xml:ns:netconf:base:1.0',
            'oc-netinst': 'http://openconfig.net/yang/network-instance',
            'oc-ni-types': 'http://openconfig.net/yang/network-instance-types',
            'oc-pol-types': 'http://openconfig.net/yang/policy-types',
            'oc-types': 'http://openconfig.net/yang/openconfig-types'}
        r = self.d.get_config(models='openconfig-network-instance')
        self.assertEqual(r.ns, expected_ns)

    def test_get_1(self):
        r = self.d.get(models='openconfig-network-instance')
        name = r.xpath('.//oc-netinst:network-instances/'
                       'oc-netinst:network-instance'
                       '[oc-netinst:name="Mgmt-intf"]'
                       '/oc-netinst:config/oc-netinst:name/text()')
        self.assertEqual(name, ['Mgmt-intf'])

