More on ConfigDelta
===================

Internally, a ConfigDelta object contains two Config objects: a source Config
instance and a destination Config instance. This allows us to calculate
equivalent diff as a Netconf edit-config, a list of Restconf Requests, or a gNMI
SetRequest. A ConfigDelta object is tightly coupled with a Config object.

create ConfigDelta objects
--------------------------

As we see in Tutorial section, a ConfigDelta object can be created by two
Config objects in a form of subtraction.

Another way, a ConfigDelta object can be instantiated from a Config object and
an edit-config.

In the following example, current device config is set to config1:

.. code-block:: text

    >>> device.nc.load_model('openconfig-system')
    ...
    >>> reply = device.nc.get_config(models='openconfig-system')
    INFO:ncclient.operations.rpc:Requesting 'GetConfig'
    >>> config1 = device.nc.extract_config(reply)
    >>>

And we plan to send an edit-config as the XML string below:

.. code-block:: text

    >>> edit_config_xml = """
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
        """
    >>> from yang.ncdiff import ConfigDelta
    >>> delta = ConfigDelta(config1, delta=edit_config_xml)
    >>>

verify the result of a ConfigDelta object
-----------------------------------------

The result of the edit-config can be predicted as config2:

.. code-block:: text

    >>> config2 = config1 + delta
    >>>

Now send the edit-config to the device and capture the real result as config3:

.. code-block:: text

    >>> reply = device.nc.edit_config(target='running', config=delta.nc)
    INFO:ncclient.operations.rpc:Requesting 'EditConfig'
    >>> reply.ok
    True
    >>> reply = device.nc.get_config(models='openconfig-system')
    INFO:ncclient.operations.rpc:Requesting 'GetConfig'
    >>> config3 = device.nc.extract_config(reply)
    >>>

Finally, ensure that config2 equals to config3 and claim the test is passed:

.. code-block:: text

    >>> config2 == config3
    True
    >>>

Additional confirmation might be achieved via CLI:

.. code-block:: text

    nyqT05#show running-config  | include aaa group server
    aaa group server radius ISE1
    nyqT05#


.. sectionauthor:: Jonathan Yang <yuekyang@cisco.com>
