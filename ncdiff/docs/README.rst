.. _yang.ncdiff:


Introduction
============

Configuration is a major object of NetConf. RFC 6241 claims "NETCONF defined in
this document provides mechanisms to install, manipulate, and delete the
configuration of network devices."

Each YANG model tries to abstract one aspect of configuration by a hierarchical
schema. There might be a model to describe OSPF configuration, and another
model to describe BGP configuration, etc.

For one model, there are many different possible configurations. Each
configuration might be considered as a state, and it can be obtained by a
get-config request. Between two states, there are two directional transitions:
from state A to state B, and from state B to state A. Each transition
corresponds to an edit-config RPC.

This module defines three classes: ModelDevice, NcConfig and NcConfigDelta.

* A modeled device supporting multiple models - ModelDevice
* A config containing data of multiple models - NcConfig
* A config delta between two configs - NcConfigDelta

Quick examples can be found in section Examples.

Features
--------

* Create an instance of ModelDevice by providing a ncclient connection
* Load model schema to an instance of ModelDevice
* ModelDevice supports get, get-config and edit-config operations
* Calculate diff of two instances of NcConfig, and the result is an instance of
  NcConfigDelta
* Calculate addition or subtraction of an instances of NcConfig and an
  instances of NcConfigDelta
* Support XPATH on GetReply, NcConfig and NcConfigDelta

Config Operations
-----------------

Summary of config operations:

===============   =========   ===============   =========   ===============   ==================================
operand           operator    operand           equality    result            note
===============   =========   ===============   =========   ===============   ==================================
NcConfig          \+          NcConfig          =           NcConfig          Combine two config
NcConfig          \+          NcConfigDelta     =           NcConfig          Apply edit-config to a config
NcConfigDelta     \+          NcConfigDelta     =           N/A               Not implemented
NcConfigDelta     \+          NcConfig          =           NcConfig          Apply edit-config to a config
NcConfig          \-          NcConfig          =           NcConfigDelta     Generate an edit-config
NcConfig          \-          NcConfigDelta     =           NcConfig          Apply an opposite edit-config
NcConfigDelta     \-          NcConfigDelta     =           N/A               Not implemented
NcConfigDelta     \-          NcConfig          =           N/A               Not implemented
===============   =========   ===============   =========   ===============   ==================================


Support Mailers
===============
Users are encouraged to contribute to yang.ncdiff module as expertise of data
model testing grows in Cisco. Any questions or requests may be sent to
yang-python@cisco.com.


Examples
========

Here are some usage examples of yang.ncdiff. They are organized in the sequence
of four classes - ModelDevice, NcConfig, NcConfigDelta, and RPCReply.

ModelDevice
-----------

Similar to `yang.connector
<http://wwwin-pyats.cisco.com/cisco-shared/yang/connector/html/>`_, users may
create a ModelDevice instance as a device connection instance. Say there is a
YAML topology file:

.. code-block:: text

    devices:
        asr22:
            type: 'ASR'
            tacacs:
                login_prompt: "login:"
                password_prompt: "Password:"
                username: "admin"
            passwords:
                tacacs: admin
                enable: admin
                line: admin
            connections:
                a:
                    protocol: telnet
                    ip: "1.2.3.4"
                    port: 2004
                vty:
                    protocol : telnet
                    ip : "2.3.4.5"
                netconf:
                    class: yang.ncdiff.ModelDevice
                    ip : "2.3.4.5"
                    port: 830
                    username: admin
                    password: admin
                    hostkey_verify: False
                    look_for_keys: False

Next, prepare Netconf connection and create an instance of ModelDevice:

.. code-block:: text

    >>> from ats.topology import loader
    >>> testbed = loader.load('/users/xxx/projects/asr22.yaml')
    >>> device = testbed.devices['asr22']
    >>> device.connect(alias='nc', via='netconf')
    >>> device.nc
    <yang.ncdiff.ModelDevice object at 0xf7c9042c>
    >>> device.nc.raise_mode = 0
    >>>

.. note::

    raise_mode is an attribute of
    `ncclient Manager
    <http://ncclient.readthedocs.io/en/latest/manager.html#manager>`_
    that defines
    `exception raising mode
    <http://ncclient.readthedocs.io/en/latest/manager.html#ncclient.manager.Manager.raise_mode>`_.
    When raise_mode = 0,
    `RPCError
    <http://ncclient.readthedocs.io/en/latest/operations.html#ncclient.operations.RPCError>`_
    exceptions are not raised if there is an rpc-error in replies.

Load multiple models:

.. code-block:: text

    >>> device.nc.load_model('/users/xxx/models/Cisco-IOS-XE-native@2017-03-24.xml')
    >>> device.nc.load_model('/users/xxx/models/openconfig-interfaces@2016-12-22.xml')
    >>> device.nc.load_model('/users/xxx/models/openconfig-network-instance@2017-01-13.xml')
    >>>

If you forget what models are loaded, check attribute models:

.. code-block:: text

    >>> device.nc.models
    ['Cisco-IOS-XE-native', 'openconfig-interfaces', 'openconfig-network-instance']
    >>>

These xml files are generated by
`YTool
<https://wiki.cisco.com/display/DDMICIA/Ytool+-+Test+Generation+for+Model-Defined+Interfaces>`_
after `Sync` button on GUI is clicked. They can be copied from your YTool
server to your local directory.

Similar to ncclient, ModelDevice supports get, get-config and edit-config, in a
simpler way:

.. code-block:: text

    >>> reply = device.nc.get(models='openconfig-network-instance')
    >>> assert(reply.ok)
    >>> print(reply)
    ...
    >>> reply = device.nc.get_config(models='openconfig-network-instance')
    >>> assert(reply.ok)
    >>> print(reply)
    ...
    >>>

You can even pull statistics or config from multiple models. For example:

.. code-block:: text

    >>> reply = device.nc.get_config(models=['openconfig-interfaces',
                                             'openconfig-network-instance'])
    >>> assert(reply.ok)
    >>> print(reply)
    ...
    >>>

It would be convenient to call edit_config() with an instance of NcConfigDelta.
More details of NcConfigDelta will be depicted in NcConfigDelta section. Assume
variable `delta` is an instance of NcConfigDelta:

.. code-block:: text

    >>> reply = device.nc.edit_config(delta, target='running')
    >>> assert(reply.ok)
    >>>

NcConfig
--------

An instance of NcConfig stores a config state. There are three ways of creating
a NcConfig instance. First, use get_config() and extract_config():

.. code-block:: text

    >>> reply = device.nc.get_config(models=['openconfig-interfaces',
                                             'openconfig-network-instance'])
    >>> config = device.nc.extract_config(reply)
    >>> config
    <yang.ncdiff.NcConfig {urn:ietf:params:xml:ns:netconf:base:1.0}config at 0xf715e40c>
    >>> print(config)
    ...
    >>>

Second, if you already have a rpc-reply in XML:

.. code-block:: text

    >>> xml = """
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
    >>> config = NcConfig(device.nc, xml)
    >>> print(config)
    ...
    >>>

Or, you have a config in XML:

.. code-block:: text

    >>> xml = """
            <config xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
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
            </config>
            """
    >>> config = NcConfig(device.nc, xml)
    >>> print(config)
    ...
    >>>

Third, if an instance of Element is available:

.. code-block:: text

    >>> config_ele
    <Element {urn:ietf:params:xml:ns:netconf:base:1.0}config at 0xf31cf2ec>
    >>> config = NcConfig(device.nc, config_ele)
    >>> config
    <yang.ncdiff.NcConfig {urn:ietf:params:xml:ns:netconf:base:1.0}config at 0xf31d1dac>
    >>> print(config)
    >>>

Internally, config information is stored in attribute `ele`, which is the
single source of truth. Users may manipulate attribute `ele` if required. And
another attribute `xml` updates automatically.

.. code-block:: text

    >>> config.ele
    <Element {urn:ietf:params:xml:ns:netconf:base:1.0}config at 0xf31d1c8c>
    >>> config.xml
    '<nc:config xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">...</nc:config>'
    >>>

NcConfig supports XPATH. Say I need port speed config of GigabitEthernet1/0/1:

.. code-block:: text

    >>> ret = config.xpath('/nc:config/oc-if:interfaces/oc-if:interface'
                           '[oc-if:name="GigabitEthernet0/0"]/oc-eth:ethernet'
                           '/oc-eth:config/oc-eth:port-speed/text()')
    >>> assert(ret[0] == 'SPEED_1GB')
    >>>

Or I want to know how many interface names start with "GigabitEthernet1/0/":

.. code-block:: text

    >>> ret = config.xpath('count(/nc:config/oc-if:interfaces/oc-if:interface'
                           '[starts-with(oc-if:name/text(),
                                         "GigabitEthernet1/0/")])')
    >>> assert(ret == 2.0)
    >>>

.. note::

    In order to facilitate xpath() and filter(), users may call ns_help() to
    view the mapping between prefixes and URLs.

NcConfig allows you to get a partial config. Traditional way is defining a
filter and calling get_config():

.. code-block:: text

    >>> from lxml import etree
    >>> f = etree.Element('{urn:ietf:params:xml:ns:netconf:base:1.0}filter',
                          type='xpath',
                          nsmap={'ios':
                                 'http://cisco.com/ns/yang/Cisco-IOS-XE-native'},
                          select=".//ios:native/ios:ntp")
    >>> reply = device.nc.get_config(filter=f)
    >>> c1 = device.nc.extract_config(reply)
    >>>

Another way is calling filter():

.. code-block:: text

    >>> reply = device.nc.get_config(models='Cisco-IOS-XE-native')
    >>> c2 = device.nc.extract_config(reply).filter('.//ios:native/ios:ntp')
    >>>

And `c1` equals to `c2`:

.. code-block:: text

    >>> c1 == c2
    True
    >>>

NcConfigDelta
-------------

An object representing the difference between two NcConfig objects.
NcConfigDelta object is directional. For instance, `delta` can be considered as
the transition from `config1` to `config2`, assuming `config1` to `config2` are
NcConfig objects:

.. code-block:: text

    >>> delta = config2 - config1
    >>> print(delta)
    ...
    >>>

If your current device config is `config1`, an edit-config can be sent out to
complete the transition to `config2`:

.. code-block:: text

    >>> reply = device.nc.edit_config(delta, target='running')
    >>> assert(reply.ok)
    >>>

Later, you may want to switch your device config back to `config1`:

.. code-block:: text

    >>> reply = device.nc.edit_config(-delta, target='running')
    >>> assert(reply.ok)
    >>>

You can confirm that your device is in state `config1` indeed:

.. code-block:: text

    >>> reply = device.nc.get_config(models='Cisco-IOS-XE-native')
    >>> config3 = device.nc.extract_config(reply)
    >>> config1 == config3
    True
    >>>

There is another use case. If you already have an edit-config in XML, a
NcConfigDelta instance can be created:

.. code-block:: text

    >>> delta_xml = """
        <rpc message-id="101" xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
          <edit-config>
            <target>
              <running/>
            </target>
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
          </edit-config>
        </rpc>
        """
    >>> delta = NcConfigDelta(device.nc, delta_xml)
    >>> delta
    <yang.ncdiff.NcConfigDelta {urn:ietf:params:xml:ns:netconf:base:1.0}config at 0xf709132c>
    >>> print(delta)
    ...
    >>> print(-delta)
    ...
    >>>

.. note::

    NcConfigDelta allows you to pass two XML strings or two Element objects in
    the constructor. One is the transition, the other one is the opposite
    direction transition. In the example above, only one XML string was passed
    in, so the opposite direction is empty.

Given the delta, yang.ncdiff can predict the result of transition from `config4`:

.. code-block:: text

    >>> config5 = config4 + delta
    >>> print(config5)
    ...
    >>>

NcConfigDelta supports xpath() and filter() as well.

.. note::

    In order to facilitate xpath() and filter(), users may call ns_help() to
    view the mapping between prefixes and URLs.

RPCReply
--------

RPCReply is originally a class in ncclient package, but it is enhanced to
support XPATH by yang.ncdiff.

RPCReply supports method xpath() but not filter().

.. code-block:: text

    >>> reply = device.nc.get(models='openconfig-network-instance')

    >>> ret = reply.xpath('/nc:rpc-reply/nc:data/oc-netinst:network-instances'
                          '/oc-netinst:network-instance/oc-netinst:interfaces'
                          '/oc-netinst:interface/oc-netinst:id/text()')
    >>> assert(set(ret) == {'GigabitEthernet0/0'})
    >>>

.. note::

    In order to facilitate xpath(), users may call ns_help() to view the
    mapping between prefixes and URLs.

In some cases, especially when receiving rpc-error, there might be some
namespaces that are not claimed in model schema. ns_help() still lists them and
make up some prefixes for you.

.. code-block:: text

    >>> reply = device.nc.edit_config(delta, target='running')
    >>> reply.ok
    False
    >>> reply.ns_help()
    >>>


Installation
============

yang.ncdiff module requires lxml and ncclient, which will be briefly described
first. Then yang.ncdiff package installation section is followed.

lxml Installation
-----------------

lxml package is available on Internet so your server may need proxy setup to
access external sites. `lab_proxy.sh` is for bash and `lab_proxy.csh` is for
csh.

.. code-block:: text

    source /auto/pyats/bin/lab_proxy.sh

Next install lxml:

.. code-block:: text

    pip install lxml

.. note::

    Depending on your system of 32-bit or 64-bit python, some other packages
    need to be installed first. Please refer to some instructions in
    `YDK Installation <https://wiki.cisco.com/display/PYATS/YDK#YDK-Installation>`_
    as YDK has very similar dependencies. Another useful resource is
    `PieStack <http://piestack.cisco.com/>`_

Verify whether lxml installation is successful (you are on the good path if you
do not see any error):

.. code-block:: text

    bash$ python
    Python 3.4.1 (default, Jul 20 2016, 07:21:38)
    [GCC 4.4.7 20120313 (Red Hat 4.4.7-16)] on linux
    Type "help", "copyright", "credits" or "license" for more information.
    >>> from lxml import etree
    >>>

ncclient Installation
---------------------

Once lxml is installed and verified, ncclient installation should be straight
forward.

.. code-block:: text

    pip install ncclient

ncdiff Installation
-------------------

This package can be installed from Cisco pypi server.

First-time installation steps:

.. code-block:: text

    pip install yang.ncdiff



Steps to upgrade to latest:

.. code-block:: text

    pip install --upgrade yang.ncdiff


.. sectionauthor:: Jonathan Yang <yuekyang@cisco.com>
