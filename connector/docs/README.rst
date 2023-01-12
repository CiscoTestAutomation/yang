.. _yang.connector:


Module yang.connector was initially developed internally in Cisco and is now available to the general public through open-source. It is integrated into the modular architecture of pyATS framework.

Docs: `https://yangconnector.readthedocs.io/en/latest/ <https://yangconnector.readthedocs.io/en/latest/>`_

GitHub: `https://github.com/CiscoTestAutomation/yang.git <https://github.com/CiscoTestAutomation/yang.git>`_


Introduction
============

This module defines a set of classes that connect to Data Model Interfaces
(DMI), in particular, an implementation of Netconf client and GNMI client. Restconf
implementation is coming soon.

Starting from version 2.0.0, yang.connector.Netconf becomes a wrapper of a
popular open-source package -
`ncclient <http://ncclient.readthedocs.io/en/latest/>`_
. As a result, all high-level APIs of ncclient are now supported by
yang.connector.Netconf class. In order to maintain backward compatibility,
request() method in yang.connector.Netconf remains. Another benefit of keeping
request() method is its flexibility of sending almost any RPC requests,
including syntax-incorrect messages, which is important for Netconf negative
test cases.

Quick examples can be found in section Examples.

Features
--------

* NETCONF v1.0 and v1.1 compliant (RFC 6241)
* NETCONF over SSH (RFC 6242) including Chunked Framing Mechanism
* `GNMI <https://github.com/openconfig/reference/blob/master/rpc/gnmi/gnmi-specification.md/>`_ v0.8.0 
* pyATS compliant
* Support of all high-level APIs of `ncclient <http://ncclient.readthedocs.io/en/latest/>`_

  This module is fully integrated into pyATS. The introduction
  of pyATS Connection Manager allows us to establish Netconf connections
  seamlessly in pyATS topology model. More details of Connection Manager can be
  found in
  `Connection Manager <https://pubhub.devnetcloud.com/media/pyats/docs/connections/manager.html>`_
  .

Upcoming features include support for
Restconf, and operational data model parser objects for Netconf and
Restconf with integration of new
`Genie <https://pubhub.devnetcloud.com/media/pyats-packages/docs/genie/index.html>`_.

Comparison to Other Netconf Clients
-----------------------------------

There are a few other Netconf client software packages available:

* `ConfD Netconf Server <http://www.tail-f.com/confd-netconf-server/>`_ includes
  a Netconf python-based client. ConfD Netconf Server is rich in features, but
  for Netconf testing purpose, it might be too heavy.
* `MG-SOFT Netconf/Yang Python Scripting System
  <http://www.mg-soft.com/mgProductsNetConf.html?p1=products>`_ is a
  **commercial** Netconf client scripting framework, which consists of three
  components: Netconf Script API, YANG Python layer, and a GUI tool that lets
  you generate Python classes from YANG modules.
* `libnetconf <https://github.com/CESNET/libnetconf>`_ is a Netconf library in
  C language and it can be used to build Netconf servers and clients.
  libnetconf has Python bindings called pynetconf that requires distutils
  Python module. libnetconf is being used by some teams in Cisco.

These netconf client software packages are all viable options to serve different
purposes. However, yang.connector is designed to integrate into pyATS
environment and to meet Cisco internal data model testing requirements.

Data Model Testing in Cisco
---------------------------

Cisco is committed to deliver device operational consistency and alignment,
full automation of device lifecycle operations, and simplicity in device
management through data model driven programmatic interfaces. Therefore,
data model testing is beginning to take hold at Cisco and its importance is
increasing. Traditional CLI-based testing is evolving when customers start to
demand more data model driven interfaces.

Yang.connector module is an attempt to respond to data model testing
needs.


Support Mailers
===============
Users are encouraged to contribute to yang.connector module as data model
testing gains momentum. Any questions or requests may be sent to
yang-python@cisco.com.


NETCONF Examples
================

Here are some usage examples of NETCONF client. `ncclient document <http://ncclient.readthedocs.io/en/latest/manager.html>`_ is always a good
starting point. `ncclient source code <https://github.com/ncclient/ncclient/tree/master/ncclient>`_
might be another great resource of understanding.

connect()
---------

Connect to Netconf interface.

Topology YAML Example:

.. code-block:: yaml

    devices:
        asr22:
            type: 'ASR'
            credentials:
                default:
                    username: admin
                    password: admin
            connections:
                a:
                    protocol: telnet
                    ip: "1.2.3.4"
                    port: 2004
                    prompts:
                        login: "login:"
                        password: "Password:"
                vty:
                    protocol : telnet
                    ip : "2.3.4.5"
                    prompts:
                        password: "Password:"
                netconf:
                    class: yang.connector.Netconf
                    ip : "2.3.4.5"
                    port: 830
                    username: admin
                    password: admin
                    credentials:
                        netconf:
                            username: ncadmin
                            password: ncpw


Python Code:

.. code-block:: python

    >>> from pyats.topology import loader
    >>> testbed = loader.load('/users/xxx/xxx/asr22.yaml')
    >>> device = testbed.devices['asr21']
    >>> device.connect(alias='nc', via='netconf')
    >>>

**Settings**

The following settings are supported for netconf connections:

    * NETCONF_SCREEN_LOGGING_MAX_LINES: (int) Max number of lines to log to the
      screen. Logs up to 40 lines by default. The device log file will contain
      all the log lines. Set to 0 to disable.
    * NETCONF_LOGGING_FORMAT_XML: (bool) Format XML or leave as-is. Enabled by
      default, set to False to disable.

You can update the settings via the settings attribute or via the testbed yaml file.

.. code-block:: python

    >>> device.nc.settings.NETCONF_SCREEN_LOGGING_MAX_LINES = 40
    >>> device.nc.settings.NETCONF_LOGGING_FORMAT_XML = True

.. code-block:: yaml

    devices:
        asr22:
            connections:
                netconf:
                    settings:
                        NETCONF_LOGGING_FORMAT_XML: True
                        NETCONF_SCREEN_LOGGING_MAX_LINES: 100


connected
---------

Whether currently connected to the NETCONF server.

Python Code:

.. code-block:: text

    >>> device.nc.connected
    True
    >>>

server_capabilities
-------------------

An object representing the server’s capabilities.

Python Code:

.. code-block:: text

    >>> for iter in device.nc.server_capabilities:
    ...     print(iter)
    ...
    urn:ietf:params:xml:ns:yang:smiv2:RFC-1215?module=RFC-1215
    urn:ietf:params:xml:ns:yang:smiv2:SNMPv2-TC?module=SNMPv2-TC
    ...
    >>>

timeout
-------

Specify the timeout for synchronous RPC requests. By default, it's 30 seconds.

Python Code:

.. code-block:: text

    >>> device.nc.timeout
    30
    >>> device.nc.timeout = 10
    >>> device.nc.timeout
    10
    >>>

get()
-----

Retrieve running configuration and device state information.

One way is by defining a subtree filter:

.. code-block:: text

    >>> from lxml import etree
    >>> ele_filter = etree.Element("{urn:ietf:params:xml:ns:netconf:base:1.0}filter",
                                   type="subtree")
    >>> ele_routing = etree.SubElement(ele_filter,
                                       "routing",
                                       nsmap = {None: 'urn:ietf:params:xml:ns:yang:ietf-routing'})
    >>> ele_routing_instance = etree.SubElement(ele_routing, "routing-instance")
    >>> ele_name = etree.SubElement(ele_routing_instance, "name").text = 'default'
    >>> device.nc.get(filter=ele_filter).data_xml

Another way is by an XPATH filter:

    >>> from lxml import etree
    >>> ele_filter = etree.Element("{urn:ietf:params:xml:ns:netconf:base:1.0}filter",
                                   type="xpath",
                                   nsmap = {None: 'urn:ietf:params:xml:ns:yang:ietf-routing'},
                                   select="/routing/routing-instance[name='default']")
    >>> device.nc.get(filter=ele_filter).data_xml


get_config()
------------

Retrieve all or part of a specified configuration. For instance, a complete
configuration of native model can be captured from an IOS-XE Polaris device:

.. code-block:: text

    >>> from lxml import etree
    >>> ele_filter = etree.Element("{urn:ietf:params:xml:ns:netconf:base:1.0}filter", type="subtree")
    >>> ele_native = etree.SubElement(ele_filter, "native",
                                      nsmap = {None: 'http://cisco.com/ns/yang/ned/ios'})
    >>> device.nc.get_config(source='running', filter=ele_filter).data_xml

If only a subtree native/aaa is needed:

.. code-block:: text

    >>> from lxml import etree
    >>> ele_filter = etree.Element("{urn:ietf:params:xml:ns:netconf:base:1.0}filter", type="subtree")
    >>> ele_native = etree.SubElement(ele_filter, "native",
                                      nsmap = {None: 'http://cisco.com/ns/yang/ned/ios'})
    >>> ele_aaa = etree.SubElement(ele_native, "aaa")
    >>> device.nc.get_config(source='running', filter=ele_filter).data_xml

Alternatively, an XPATH filter can be used:

    >>> from lxml import etree
    >>> ele_filter = etree.Element("{urn:ietf:params:xml:ns:netconf:base:1.0}filter",
                                   type="xpath",
                                   nsmap = {None: 'urn:ietf:params:xml:ns:yang:ietf-interfaces'},
                                   select="/interfaces/interface[name='TenGigabitEthernet0/1/0']")
    >>> device.nc.get_config(source='running', filter=ele_filter).data_xml

edit_config()
-------------

Load all or part of the specified config to the target configuration
datastore.

XML string is straightforward. Let's add a description to an interface:

.. code-block:: text

    >>> snippet = """
        <config xmlns:xc="urn:ietf:params:xml:ns:netconf:base:1.0">
          <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
            <interface>
              <name>GigabitEthernet0/0/0</name>
              <description>This is another test</description>
            </interface>
          </interfaces>
        </config>
        """
    >>> device.nc.edit_config(target='running', config=snippet)
    <?xml version="1.0" encoding="UTF-8"?>
    <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"
               message-id="urn:uuid:95152e3f-5956-451e-9b05-7dd156b84237"
               xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
    <ok/>
    </rpc-reply>
    >>>

And then delete the description:

.. code-block:: text

    >>> snippet = """
        <config xmlns:xc="urn:ietf:params:xml:ns:netconf:base:1.0">
          <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
            <interface>
              <name>GigabitEthernet0/0/0</name>
              <description xc:operation="delete"></description>
            </interface>
          </interfaces>
        </config>
        """
    >>> device.nc.edit_config(target='running', config=snippet)
    <?xml version="1.0" encoding="UTF-8"?>
    <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"
               message-id="urn:uuid:d1e831a0-c861-4f48-8363-fbfae2c7b737"
               xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
    <ok/>
    </rpc-reply>
    >>>

Same thing can be achieved in ElementTree format:

.. code-block:: text

    >>> from lxml import etree
    >>> ns_map = "urn:ietf:params:xml:ns:netconf:base:1.0"
    >>> ele_config = etree.Element("{%s}config" % ns_map)
    >>> ele_interfaces = etree.SubElement(ele_config, "interfaces",
                                          nsmap = {None: 'urn:ietf:params:xml:ns:yang:ietf-interfaces'})
    >>> ele_interface = etree.SubElement(ele_interfaces, "interface")
    >>> ele_name = etree.SubElement(ele_interface, "name").text = 'GigabitEthernet0/0/0'
    >>> ele_description = etree.SubElement(ele_interface, "description").text = 'This is another test'
    >>> device.nc.edit_config(target='running', config=ele_config)
    <?xml version="1.0" encoding="UTF-8"?>
    <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"
               message-id="urn:uuid:ece6ba69-f053-4aa6-b487-98b92c5e9ed5"
               xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
    <ok/>
    </rpc-reply>
    >>>

request()
---------

Send any RPC request in string format and return RPC reply in string. The
request can be either syntax correct or incorrect, yang.connector.Netconf will
send it out anyway.

This RPC returns configuration of interface TenGigabitEthernet0/1/0:

.. code-block:: text

    >>> rpc_request = """
    ...     <rpc message-id="101" xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
    ...       <get-config>
    ...         <source>
    ...           <running/>
    ...         </source>
    ...         <filter type="subtree">
    ...           <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
    ...             <interface>
    ...               <name>TenGigabitEthernet0/1/0</name>
    ...             </interface>
    ...           </interfaces>
    ...         </filter>
    ...       </get-config>
    ...     </rpc>
    ...     """
    >>> reply = device.nc.request(rpc_request, timeout=40)
    >>> print(reply)
    <?xml version="1.0" encoding="UTF-8"?>
    <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="101">
    <data>
    <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
    <interface>
    <name>TenGigabitEthernet0/1/0</name>
    <type xmlns:ianaift="urn:ietf:params:xml:ns:yang:iana-if-type">ianaift:ethernetCsmacd</type>
    <enabled>false</enabled>
    <ipv4 xmlns="urn:ietf:params:xml:ns:yang:ietf-ip"></ipv4>
    <ipv6 xmlns="urn:ietf:params:xml:ns:yang:ietf-ip"></ipv6>
    </interface>
    </interfaces>
    </data>
    </rpc-reply>
    >>>

get_schema()
------------

Retrieve schema from the device if the device supports RFC 6022.

.. code-block:: text

    >>> reply = device.nc.get_schema('ietf-interfaces')
    >>> print(reply.data)

disconnect()
------------

Close the transport session.

Python Code:

.. code-block:: text

    >>> device.nc.connected
    True
    >>> device.nc.disconnect()
    >>> device.nc.connected
    False
    >>>

close_session()
---------------

Request graceful termination of the NETCONF session, and also close the
transport.

Python Code:

.. code-block:: text

    device.nc.disconnect()

    >>> device.nc.connected
    True
    >>> device.nc.close_session()
    <?xml version="1.0" encoding="UTF-8"?>
    <rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"
               message-id="urn:uuid:ec65cce3-f8de-4710-b9ed-dd3501e36639"
               xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
    <ok/>
    </rpc-reply>
    >>> device.nc.connected
    False
    >>> device.nc.connect()
    >>>

GNMI Examples
========
Here are some usage examples of GNMI client. For more details see `API Refernce <https://yangconnector.readthedocs.io/en/latest/apidocs.html>`_.

Python Code:

.. code-block:: text

    >>> from pyats.topology import loader
    >>> from yang.connector.gnmi import Gnmi
    >>> testbed=loader.load('testbed.static.yaml')
    >>> device=testbed.devices['uut']
    >>> device.connect(alias='gnmi', via='yang2')

    >>> resp=device.capabilities()
    >>> resp.gNMI_version
    '0.7.0'
    >>>

Installation
============

yang.connector module requires pyATS.

It can be installed from pypi server.

.. code-block:: text

    pip install yang.connector

To upgrade to the latest:

.. code-block:: text

    pip install --upgrade yang.connector


.. sectionauthor:: Jonathan Yang <yuekyang@cisco.com>
