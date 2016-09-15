import logging

logging.basicConfig(level='INFO')

from ats.topology import loader

tb = loader.load('asr22.yaml')

uut = tb.devices['asr22']

uut.connect(via='netconf')


#xml = '''
#        <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces"/>
#'''
#print(uut.get(('subtree', xml)))

rpc = '''
<get>
    <filter>
      <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces"/>
    </filter>
</get>
'''

#print(uut.dispatch(rpc))

from lxml import etree
namespace = "urn:ietf:params:xml:ns:netconf:base:1.0"

get = etree.Element('get')
filter = etree.SubElement(get, 'filter')
interfaces=etree.SubElement(filter, 'interfaces', 
                            nsmap={None:"urn:ietf:params:xml:ns:yang:ietf-interfaces"})
                            
#c = uut.dispatch(get)
#print(c)

netconf_request = """
    <rpc message-id="101"
      xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
<get>
    <filter>
      <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces"/>
    </filter>
</get>
    </rpc>
"""

reply = uut.request(netconf_request)
print(reply, type(reply), )

import code
code.interact(local=locals())

uut.disconnect()