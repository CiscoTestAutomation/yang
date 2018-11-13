gNMI SetRequest
===============

ConfigDelta objects have an attribute 'gnmi', which is a gNMI SetRequest.
It can achieve the same transaction as a Netconf edit-config does.

gNMI specification can be found `here
<https://github.com/openconfig/reference/blob/master/rpc/gnmi/gnmi-specification.md>`_.


connect to gNMI
---------------

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
                gnmi:
                    class: yang.connector.gNMI
                    ip : "2.3.4.5"
                    port: 50052
                    timeout: 10

Connect to gNMI by yang.connector.gNMI class:

.. code-block:: text

    >>> device.connect(alias='gnmi', via='gnmi')
    >>>

peek at SetRequest
------------------

Take a look at the gNMI SetRequest if there is an instance of ConfigDelta:

.. code-block:: text

    >>> print(delta.gnmi)
    update {
      path {
        elem {
          name: "oc-sys:system"
        }
        elem {
          name: "aaa"
        }
        elem {
          name: "server-groups"
        }
      }
      val {
        json_val: "{\"openconfig-system:server-group\": {\"name\": \"ISE1\", \"config\": {\"name\": \"ISE1\", \"type\": \"openconfig-aaa:RADIUS\"}}}"
      }
    }
    >>>

send SetRequest
---------------

All you have to do is sending the gNMI SetRequest:

.. code-block:: text

    >>> reply = device.gnmi.set(delta.gnmi)
    >>> print(reply)
    response {
      path {
        elem {
          name: "oc-sys:system"
        }
        elem {
          name: "aaa"
        }
        elem {
          name: "server-groups"
        }
      }
      op: UPDATE
    }
    timestamp: 1523462310023046066
    >>>

Check the device config by CLI, Netconf, Restconf or gNMI. It should be
changed!


.. sectionauthor:: Jonathan Yang <yuekyang@cisco.com>
