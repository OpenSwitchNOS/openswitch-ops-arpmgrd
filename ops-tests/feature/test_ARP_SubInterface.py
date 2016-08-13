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
Test_name: test_ARP_SubInterface
Test_Description: Test to verify arp, ip route and rib tables are populated
    correctly when subinterfaces are configured.
"""
from __future__ import unicode_literals, absolute_import
from __future__ import print_function, division
from pytest import mark

TOPOLOGY = """
# +-------+                                 +-------+
# |       |     +-------+     +-------+     |       |
# |  hs1  <----->  sw1  <----->  sw2  <----->  hs2  |
# |       |     +-------+     +-------+     |       |
# +-------+                                 +-------+
#

# Nodes
[type=openswitch name="Switch 1"] sw1
[type=openswitch name="Switch 2"] sw2
[type=host name="Host 1"] hs1
[type=host name="Host 2"] hs2

# Links
hs1:if03 -- sw1:if01
sw1:if02 -- sw2:if02
sw2:if01 -- hs2:if03
"""
vlan_id = 10
sw1ip1 = '100.1.1.1/24'
sw1ip2 = '200.1.1.1/24'
sw1_dest_prefix = '100.1.2.0/24'
sw1_next_hop = '200.1.1.2'
sw2ip1 = '100.1.2.1/24'
sw2ip2 = '200.1.1.2/24'
sw2_dest_prefix = '100.1.1.0/24'
sw2_next_hop = '200.1.1.1'


def ops_config(sw, ip1, ip2, dest_prefix, next_hop, vlan_id, step):
    step('### Config DUT setting ###')
    with sw.libs.vtysh.ConfigInterface('if01') as ctx:
        ctx.no_shutdown()
        ctx.ip_address(ip1)
    with sw.libs.vtysh.ConfigInterface('if02') as ctx:
        ctx.no_shutdown()
    with sw.libs.vtysh.ConfigSubinterface('if02', vlan_id) as ctx:
        ctx.no_shutdown()
        ctx.ip_address(ip2)
        ctx.encapsulation_dot1_q(vlan_id)
    with sw.libs.vtysh.Configure() as ctx:
        ctx.ip_route(dest_prefix, next_hop)
    # print(sw.ports('if01'))
    print(sw.ports.get('if01'))


def hosts_config(hs1, hs2, step):
    h1p1 = hs1.ports['if03']
    h2p1 = hs2.ports['if03']

    step("Config the Hosts")
    ifconfig = hs1("ifconfig {h1p1}".format(**locals()))
    words = ifconfig.split()
    if "HWaddr" in words:
        mac_hs1 = words[words.index("HWaddr") + 1]
    else:
        mac_hs1 = None

    ifconfig = hs2("ifconfig {h2p1}".format(**locals()))
    words = ifconfig.split()
    if "HWaddr" in words:
        mac_hs2 = words[words.index("HWaddr") + 1]
    else:
        mac_hs2 = None

    # Configure host 1
    print("Configuring host 1 with ip1\n")
    hs1.libs.ip.interface('if03', addr='100.1.1.2/24', up=True)
    hs1("ip -4 route add 100.1.2.0/24 via 100.1.1.1")

    # Configure host 2
    print("Configuring host 2 with 100.1.2.2/24\n")
    hs2.libs.ip.interface('if03', addr='100.1.2.2/24', up=True)
    hs2("ip -4 route add 100.1.1.0/24 via 100.1.2.1")

    return [mac_hs1, mac_hs2]


def arp_verify_ovsdb_results_sw1(
        sw, hs1, hs2, sw_mac1, mac_hs, sw_ip2, hs_ip1, step):
    step("Verify show arp results")
    result1 = sw.libs.vtysh.show_arp()
    print(result1)
    mac = result1[hs_ip1]['mac_address']
    assert mac == mac_hs, 'Mac address mismatched/not learnt'
    port = result1[hs_ip1]['port']
    assert port == sw.ports.get('if01'), 'Port info mismatched/not learnt'
    state = result1[hs_ip1]['state']
    assert state == 'reachable', 'ARP state failed/stale'

    mac = result1[sw_ip2]['mac_address']
    assert mac == sw_mac1, 'Mac address mismatched/not learnt'
    port = result1[sw_ip2]['port']
    assert port == sw.ports.get(
        'if02') + '.10', 'Port info mismatched/not learnt'
    state = result1[sw_ip2]['state']
    assert state == 'reachable', 'ARP state failed/stale'
    print('Show arp denotes that ' + hs_ip1 + ' and ' + sw_ip2 + ' \
    are reachable by Switch1')

    step("Verify show ip_route results")
    result2 = sw.libs.vtysh.show_ip_route()
    print(result2)

    result2[0]['id'] == '100.1.1.0'
    result2[0]['next_hops'][0]['via'] == sw.ports.get('if01')
    result2[0]['next_hops'][0]['from'] == 'connected'
    result2[1]['id'] == '100.1.2.0'
    result2[1]['next_hops'][0]['via'] == sw_ip2
    result2[1]['next_hops'][0]['from'] == 'static'
    result2[2]['id'] == '200.1.1.0'
    result2[2]['next_hops'][0]['via'] == sw.ports.get('if02') + '.10'
    result2[2]['next_hops'][0]['from'] == 'connected'
    print('Show ip route denotes that ' + hs_ip1 + ' and ' + sw_ip2 + ' \
    are connected to Switch')

    step("Verify show rib results")
    result3 = sw.libs.vtysh.show_rib()
    print(result3)

    result3['ipv4_entries'][0]['id'] == '100.1.1.0'
    result3['ipv4_entries'][0]['next_hops'][0]['via'] == sw.ports.get('if01')
    result3['ipv4_entries'][0]['next_hops'][0]['from'] == 'connected'
    result3['ipv4_entries'][1]['id'] == '100.1.2.0'
    result3['ipv4_entries'][1]['next_hops'][0]['via'] == sw_ip2
    result3['ipv4_entries'][1]['next_hops'][0]['from'] == 'static'
    result3['ipv4_entries'][0]['id'] == '200.1.1.0'
    result3['ipv4_entries'][0]['next_hops'][0]['via'] == sw.ports.get(
        'if02') + '.10'
    result3['ipv4_entries'][0]['next_hops'][0]['from'] == 'connected'
    print('Show rib denotes that ' + hs_ip1 + ' and ' + sw_ip2 + ' \
    are connected to Switch')


def arp_verify_ovsdb_results_sw2(
        sw, hs1, hs2, sw_mac1, mac_hs, sw_ip1, hs_ip2, step):
    step("Verify show arp results")
    result1 = sw.libs.vtysh.show_arp()
    print(result1)
    mac = result1[hs_ip2]['mac_address']
    assert mac == mac_hs, 'Mac address mismatched/not learnt'
    port = result1[hs_ip2]['port']
    assert port == sw.ports.get('if01'), 'Port info mismatched/not learnt'
    state = result1[hs_ip2]['state']
    assert state == 'reachable', 'ARP state failed/stale'

    mac = result1[sw_ip1]['mac_address']
    assert mac == sw_mac1, 'Mac address mismatched/not learnt'
    port = result1[sw_ip1]['port']
    assert port == sw.ports.get(
        'if02') + '.10', 'Port info mismatched/not learnt'
    state = result1[sw_ip1]['state']
    assert state == 'reachable', 'ARP state failed/stale'
    print('Show arp denotes that ' + hs_ip2 + ' and ' + sw_ip1 + ' \
    are reachable by Switch')

    step("Verify show ip_route results")
    result2 = sw.libs.vtysh.show_ip_route()
    print(result2)

    result2[0]['id'] == '100.1.1.0'
    result2[0]['next_hops'][0]['via'] == sw_ip1
    result2[0]['next_hops'][0]['from'] == 'static'
    result2[1]['id'] == '100.1.2.0'
    result2[1]['next_hops'][0]['via'] == sw.ports.get('if01')
    result2[1]['next_hops'][0]['from'] == 'connected'
    result2[2]['id'] == '200.1.1.0'
    result2[2]['next_hops'][0]['via'] == sw.ports.get('if02') + '.10'
    result2[2]['next_hops'][0]['from'] == 'connected'
    print('Show ip route denotes that ' + hs_ip2 + ' and ' + sw_ip1 + ' \
    are connected to Switch')

    step("Verify show rib results")
    result3 = sw.libs.vtysh.show_rib()
    print(result3)

    result3['ipv4_entries'][0]['id'] == '100.1.1.0'
    result3['ipv4_entries'][0]['next_hops'][0]['via'] == sw_ip1
    result3['ipv4_entries'][0]['next_hops'][0]['from'] == 'static'
    result3['ipv4_entries'][1]['id'] == '100.1.2.0'
    result3['ipv4_entries'][1]['next_hops'][0]['via'] == sw.ports.get('if01')
    result3['ipv4_entries'][1]['next_hops'][0]['from'] == 'connected'
    result3['ipv4_entries'][0]['id'] == '200.1.1.0'
    result3['ipv4_entries'][0]['next_hops'][0]['via'] == sw.ports.get(
        'if02') + '.10'
    result3['ipv4_entries'][0]['next_hops'][0]['from'] == 'connected'
    print('Show rib denotes that ' + hs_ip2 + ' and ' + sw_ip1 + ' \
    are connected to Switch')


@mark.platform_incompatible(['docker'])
def test_arp_subinterface(topology, step):
    sw1 = topology.get('sw1')
    sw2 = topology.get('sw2')
    hs1 = topology.get('hs1')
    hs2 = topology.get('hs2')

    assert sw1 is not None
    assert sw2 is not None
    assert hs1 is not None
    assert hs2 is not None

    step('Config the devices')
    ops_config(
        sw1, sw1ip1, sw1ip2, sw1_dest_prefix, sw1_next_hop, vlan_id, step)
    ops_config(
        sw2, sw2ip1, sw2ip2, sw2_dest_prefix, sw2_next_hop, vlan_id, step)
    [mac_hs1, mac_hs2] = hosts_config(hs1, hs2, step)

    sw1_sub_int = sw1.libs.vtysh.show_interface_subinterface('if02')
    print(sw1_sub_int)
    sw1_mac1 = sw1_sub_int[10]['mac_address']
    sw2_sub_int = sw2.libs.vtysh.show_interface_subinterface('if02')
    sw2_mac1 = sw2_sub_int[10]['mac_address']

    # Ping from host 1 to switch
    print("Ping s1 from hs1\n")
    output = hs1.libs.ping.ping(10, "100.1.1.1")
    assert output['transmitted'] == output['received']

    # Ping from host 2 to switch
    print("Ping s1 from hs2\n")
    output = hs2.libs.ping.ping(10, "100.1.2.1")
    assert output['transmitted'] == output['received']

    # Ping from host 1 to host 2
    print("Ping hs2 from hs1\n")
    output = hs1.libs.ping.ping(10, "100.1.2.2")
    assert output['transmitted'] == output['received']

    # Ping from host 2 to host 1
    print("Ping hs1 from hs2\n")
    output = hs2.libs.ping.ping(10, "100.1.1.2")
    assert output['transmitted'] == output['received']

    arp_verify_ovsdb_results_sw1(
        sw1, hs1, hs2, sw2_mac1, mac_hs1, '200.1.1.2', '100.1.1.2', step)
    arp_verify_ovsdb_results_sw2(
        sw2, hs1, hs2, sw1_mac1, mac_hs2, '200.1.1.1', '100.1.2.2', step)
