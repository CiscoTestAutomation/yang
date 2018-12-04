Tutorial
========

Here are some basic usage examples of yang.ncdiff. They are organized in the
sequence of a typical use case - connect device, load models, get or get-config,
and edit-config.

connect to a Netconf device
---------------------------

Similar to `yang.connector
<https://yangconnector.readthedocs.io/en/latest/>`_, users may
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

    >>> from pyats.topology import loader
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

Set timeout if needed:

.. code-block:: text

    >>> device.nc.timeout = 120
    >>> device.nc.timeout
    120
    >>>

Download and scan models:

.. code-block:: text

    >>> device.nc.scan_models()
    ...
    >>>

.. note::

    By default, a folder ./yang will be created to accommodate YANG files
    downloaded.


load models
-----------

Find what models are available:

.. code-block:: text

    >>> device.nc.models_loadable
    ['BGP4-MIB', 'BRIDGE-MIB', ...]
    >>>

Load multiple models depending on your testing requirement:

.. code-block:: text

    >>> m1 = device.nc.load_model('Cisco-IOS-XE-native')
    >>> m2 = device.nc.load_model('openconfig-interfaces')
    >>> m3 = device.nc.load_model('openconfig-network-instance')
    >>>

Print out model tree:

.. code-block:: text

    >>> print(m1)
    module: Cisco-IOS-XE-native
        +--rw native
           +--rw default
           |  +--rw crypto
           |     +--rw ikev2
           |        +--rw proposal?   empty
           |        +--rw policy?     empty
    ...
    >>>


If you forget what models are loaded, check attribute 'models_loaded':

.. code-block:: text

    >>> device.nc.models_loaded
    ['Cisco-IOS-XE-native', 'cisco-ia', 'openconfig-interfaces', 'openconfig-network-instance']
    >>>

get
---

Since ModelDevice is a sub-class of
`ncclient Manager <http://ncclient.readthedocs.io/en/latest/manager.html#manager>`_,
it supports get, get-config, edit-config, and all other methods supported by
ncclient. On top of that, yang.ncdiff adds a new argument 'models' to method
get() and get_config():

.. code-block:: text

    >>> reply = device.nc.get(models='openconfig-network-instance')
    >>> assert(reply.ok)
    >>> print(reply)
    ...
    >>>

You can even pull operational data or config from multiple models. For example:

.. code-block:: text

    >>> reply = device.nc.get(models=['openconfig-interfaces',
                                      'openconfig-network-instance'])
    >>> assert(reply.ok)
    >>> print(reply)
    ...
    >>>

get-config
----------

Config state can be captured by ModelDevice method extract_config():

.. code-block:: text

    >>> reply = device.nc.get_config(models=['openconfig-interfaces',
                                             'openconfig-network-instance'])
    >>> assert(reply.ok)
    >>> config1 = device.nc.extract_config(reply)
    >>> print(config1)
    <nc:config xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
      <interfaces xmlns="http://openconfig.net/yang/interfaces">
    ...
    >>>

edit-config
-----------

Assume there are two instances of Config: config1 and config2. Make sure they
are different:

.. code-block:: text

    >>> config1 == config2
    False
    >>> delta = config2 - config1
    >>> print(delta)
    <nc:config xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
      <system xmlns="http://openconfig.net/yang/system">
        <aaa>
          <server-groups>
            <server-group>
              <name>ISE1</name>
              <config>
                <name>ISE1</name>
                <type xmlns:oc-aaa="http://openconfig.net/yang/aaa">oc-aaa:RADIUS</type>
              </config>
            </server-group>
          </server-groups>
        </aaa>
      </system>
    </nc:config>
    >>>

If the current config state is config2, a Netconf transaction to config1 can be
achieved by an edit-config '-delta':

.. code-block:: text

    >>> reply = device.nc.edit_config(target='running', config=(-delta).nc)
    INFO:ncclient.operations.rpc:Requesting 'EditConfig'
    >>> assert(reply.ok)
    >>>

Hey, check your device, its config should be config1 now!

.. code-block:: text

    >>> reply = device.nc.get_config(models='openconfig-system')
    INFO:ncclient.operations.rpc:Requesting 'GetConfig'
    >>> config = device.nc.extract_config(reply)
    >>> config == config1
    True
    >>>

Want to switch back to config2? No problem! Send 'delta':

.. code-block:: text

    >>> reply = device.nc.edit_config(target='running', config=delta.nc)
    INFO:ncclient.operations.rpc:Requesting 'EditConfig'
    >>> assert(reply.ok)
    >>>
    >>> reply = device.nc.get_config(models='openconfig-system')
    INFO:ncclient.operations.rpc:Requesting 'GetConfig'
    >>> config = device.nc.extract_config(reply)
    >>> config == config2
    True
    >>>


.. sectionauthor:: Jonathan Yang <yuekyang@cisco.com>
