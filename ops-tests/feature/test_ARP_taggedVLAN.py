# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 Hewlett Packard Enterprise Development LP
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

"""
Test_name: test_ARP_taggedVLAN
Test_Description: Test to verify arp, ip route and rib tables are populated
    correctly when tagged VLANs are configured.
"""
from __future__ import unicode_literals, absolute_import
from __future__ import print_function, division
from pytest import mark
from time import sleep

TOPOLOGY = """
#
# +-------+                  +-------+
# |       |     +-------+    |       |
# |  hs1  <----->  sw1  <---->  hs2  |
# |       |     +-------+    |       |
# +-------+                  +-------+
#

# Nodes
[type=openswitch name="Switch 1"] sw1
[type=host name="host 1"] hs1
[type=host name="host 2"] hs2

# Links
sw1:1 -- hs1:1
sw1:2 -- hs2:1
"""


# mac addresses for host 1 and host 2
mac1 = None
mac2 = None
vlan10 = '10'
vlan20 = '20'
vlan_ip1 = '100.1.1.1/24'
vlan_ip2 = '100.1.2.1/24'
ip1 = '100.1.1.2'
ip2 = '100.1.2.2'


def ops_config(sw, vlan10, vlan20, vlan_ip1, vlan_ip2, step):
    """
    untagged ports under two vlans
    :param sw: A topology node of type 'Switch'
    :param vlan: vlan id to create Vlan
    :param vlan_ip: ip address for Vlan Interface
    """
    step('### Config DUT setting ###')
    print('\nCreating Vlans on DUT')
    with sw.libs.vtysh.ConfigVlan(vlan10) as ctx:
        ctx.no_shutdown()
    with sw.libs.vtysh.ConfigVlan(vlan20) as ctx:
        ctx.no_shutdown()
    with sw.libs.vtysh.ConfigInterfaceVlan(vlan10) as ctx:
        ctx.no_shutdown()
        ctx.ip_address(vlan_ip1)
    with sw.libs.vtysh.ConfigInterfaceVlan(vlan20) as ctx:
        ctx.no_shutdown()
        ctx.ip_address(vlan_ip2)
    print('\nConfig interface dut interface 1')
    with sw.libs.vtysh.ConfigInterface('1') as ctx:
        ctx.no_routing()
        ctx.vlan_trunk_allowed(vlan10)
        ctx.no_shutdown()
    print('\nConfig interface dut interface 2')
    with sw.libs.vtysh.ConfigInterface('2') as ctx:
        ctx.no_routing()
        ctx.vlan_trunk_allowed(vlan20)
        ctx.no_shutdown()


def arpmgr_config(sw1, hs1, hs2, step):
    global mac1
    global mac2
    sw1p1 = sw1.ports['1']
    sw1p2 = sw1.ports['2']
    h1p1 = hs1.ports['1']
    h2p1 = hs2.ports['1']

    step("Config the DUT")
    ops_config(sw1, vlan10, vlan20, vlan_ip1, vlan_ip2, step)

    step("Config the Hosts")
    ifconfig = hs1("ifconfig {h1p1}".format(**locals()))
    words = ifconfig.split()
    if "HWaddr" in words:
        mac1 = words[words.index("HWaddr") + 1]
    else:
        mac1 = None

    ifconfig = hs2("ifconfig {h2p1}".format(**locals()))
    words = ifconfig.split()
    if "HWaddr" in words:
        mac2 = words[words.index("HWaddr") + 1]
    else:
        mac2 = None

    # Configure host 1
    print("Configuring host 1 with ip1\n")
    hs1('apt-get install vlan')
    hs1("modprobe 8021q")
    hs1('vconfig add eth1 10')
    # hs1.libs.ip.interface('1.10', addr='100.1.1.2/24', up=True)
    hs1('ip addr add 100.1.1.2/24 dev eth1.10')
    hs1('ip link set dev eth1.10 up')
    hs1('ip -4 route add 100.1.2.0/24 via 100.1.1.1')

    # Configure host 2
    print("Configuring host 2 with 100.1.2.2/24\n")
    hs2('apt-get install vlan')
    hs2("modprobe 8021q")
    hs2('vconfig add eth1 20')
    # hs2.libs.ip.interface('1.20', addr='100.1.2.2/24', up=True)
    hs2('ip addr add 100.1.2.2/24 dev eth1.20')
    hs2('ip link set dev eth1.20 up')
    hs2("ip -4 route add 100.1.1.0/24 via 100.1.2.1")


def arp_verify_ovsdb_results(sw1, hs1, hs2, step):
    step("Verify show arp results")
    sleep(10)
    result1 = sw1.libs.vtysh.show_arp()
    print(result1)
    mac = result1[ip1]['mac_address']
    assert mac == mac1, 'Mac address mismatched/not learnt'
    port = result1[ip1]['port']
    assert port == 'vlan10', 'Port info mismatched/not learnt'
    state = result1[ip1]['state']
    assert state == 'reachable', 'ARP state failed/stale'

    mac = result1[ip2]['mac_address']
    assert mac == mac2, 'Mac address mismatched/not learnt'
    port = result1[ip2]['port']
    assert port == 'vlan20', 'Port info mismatched/not learnt'
    state = result1[ip2]['state']
    assert state == 'reachable', 'ARP state failed/stale'
    print('Show arp denotes that ' + ip1 + ' and ' + ip2 + ' \
    are reachable by Switch')

    step("Verify show ip_route results")
    result2 = sw1.libs.vtysh.show_ip_route()
    print(result2)
    result2[0]['id'] == '100.1.1.0'
    result2[0]['next_hops'][0]['via'] == 'vlan10'
    result2[0]['next_hops'][0]['from'] == 'connected'
    result2[1]['id'] == '100.1.2.0'
    result2[1]['next_hops'][0]['via'] == 'vlan20'
    result2[1]['next_hops'][0]['from'] == 'connected'
    print('Show ip route denotes that ' + ip1 + ' and ' + ip2 + ' \
    are connected to Switch')
    step("Verify show rib results")
    result3 = sw1.libs.vtysh.show_rib()
    print(result3)
    result3['ipv4_entries'][0]['id'] == '100.1.1.0'
    result3['ipv4_entries'][0]['next_hops'][0]['via'] == 'vlan10'
    result3['ipv4_entries'][0]['next_hops'][0]['from'] == 'connected'
    result3['ipv4_entries'][1]['id'] == '100.1.2.0'
    result3['ipv4_entries'][1]['next_hops'][0]['via'] == 'vlan20'
    result3['ipv4_entries'][1]['next_hops'][0]['from'] == 'connected'
    print('Show rib denotes that ' + ip1 + ' and ' + ip2 + ' \
    are connected to Switch')


@mark.platform_incompatible(['docker'])
def test_arp_taggedvlan(topology, step):
    sw1 = topology.get('sw1')
    hs1 = topology.get('hs1')
    hs2 = topology.get('hs2')

    assert sw1 is not None
    assert hs1 is not None
    assert hs2 is not None

    arpmgr_config(sw1, hs1, hs2, step)

    # Ping from host 1 to switch
    print("Ping s1 from hs1\n")
    output = hs1.libs.ping.ping(5, "100.1.1.1")
    assert output['transmitted'] == output['received']

    # Ping from host 2 to switch
    print("Ping s1 from hs2\n")
    output = hs2.libs.ping.ping(5, "100.1.2.1")
    assert output['transmitted'] == output['received']

    # Ping from host 1 to host 2
    print("Ping hs2 from hs1\n")
    output = hs1.libs.ping.ping(5, "100.1.2.2")
    assert output['transmitted'] == output['received']

    arp_verify_ovsdb_results(sw1, hs1, hs2, step)
