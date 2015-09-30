High level design of ops-arpmgrd
================================

The ops-arpmgrd process receives neighbor notifications from kernel and manages rows in the Neighbor database table.

Responsibilities
-----------------
The ops-arpmgrd process is responsible for monitoring neighbor entries in kernel (IPv4 and IPv6) and update the Neighbor table with the neighbor entries. This daemon also refreshes kernel entries for neighbor with active traffic in datapath.

Design choices
-----------------
The ops-arpmgrd process was added to the OpenSwitch architecture in order to leverage Linux kernel for neighbor management and learning. The role of ops-arpmgrd is to keep the Neighbor table in sync with Linux neighbor entries. We rely on Linux to learn new neighbors in slow path. Once learnt, subsequent traffic will flow the datapath and not through kernel. Hence, ops-arpmgrd is also responsible for keeping these entries up to date. For inactive neighbors, we rely on Linux to ageout the neighbors. Another option for managing neighbors was to write arpmgrd functionality in ops-vswitchd with callbacks from vendor specific plugins to handle ARP and ND packets and maintain the neighbor states. This approach would have been platform specific and not platform independent.

Relationships to external OpenSwitch entities
---------------------------------------------
```ditaa
+--------+
|database+-----------+
+-+-^----+           |
  | |                |
  | |                |
+-v-+-------+  +-----v-----+
|ops-arpmgrd|  |ops-switchd|
+---^-------+  +-----+-----+
  | |                |
  | |                |
+-v-+--------+  +----v------+
|Linux Kernel|  |ops-switchd|
+------------+  +-----+-----+

```

The ops-arpmgrd registers for notifications from kernel for neighbor updates using Netlink sockets. The daemon receives messages for new neighbor, modified neighbor (state change), deleted neighbor. On receiving a notification, ops-arpmgrd updates it local cache and then updates the Neighbor table in OVSDB. The ops-arpmgrd also monitors other_config:dp_hit column of Neighbor table which is updated by ops-vswitchd. This key is updated to `true` if there is traffic for the neighbor in datapath. If this value is `true` ops-arpmgrd triggers kernel to probe for neighbor when entry goes to `stale` state.

The ops-vswitchd will register for Neighbor table updates and will program the ASIC with new neighbors and delete ASIC entries for deleted neighbors or neighbors in `failed` state.

OVSDB-Schema
------------
### Neighbor table
* vrf:
  The VRF on which this neighbor was learnt on. Currently OpenSwitch supports only one VRF.
* ip_address:
  IPv4 or IPv6 address of neighbor
* address_family:
  IPv4 or IPv6
* mac:
  MAC address of neigbor if neighbor is successfully resolved. If neighbor resolution fails, this column will be empty
* port:
  The port on which the neighbor was resolved.
* state:
  Neighbor states can be one of the following: reachable, stale, failed. Static/Permanent entries are not yet supported.
* status:
  The ops-arpmgrd process monitors the `status:dp_hit` field in the Subsystem table to determine active traffic in datapath for neighbor. If traffic is active, ops-arpmgrd will set kernel state of neighbor to `delay`, which schedules neighbor probes to refresh the kernel entry.

Code Design
-----------
* initialization: Subscribe to database tables and columns, and general initialization.
* main loop
  * reconfigure: Process changes to `status:dp_hit` column for any neighbor. If `status:dp_hit` got modified to `true` set state of neighbor entry in kernel to `delay` so that kernel schedules an neighbor probe.
  * run: Receive netlink message on netlink socket registered with RTMGRP_NEIGH group for neighbor updates from kernel. The ops-arpmgrd process handles receiving of the following Netlink message types: RTM_NEWNEIGH, RTM_DELNEIGH. Neighbor add, neighbor state modification and neighbor deletes are first updated in local cache `all_neighbors` and then updated to database.
  * handle restartability and transaction failures: To handle restartability and transaction failures ops-arpmgrd uses same approach. A new transaction is created in either case, and we do complete resync of kernel with OVSDB in this new transaction. The resync is optimized in the following way:
     - Populate local cache `all_neighbors` with kernel entries
     - Create a hash of OVSDB entries
     - Loop over list of local_cache, and if entry is not present in OVSDB entry hash, create new row, else modify existing row.
     - Loop over OVSDB entries and lookup local_cache. If entry is not found, delete the neighbor from OVSDB.

References
----------
* [Linux kernel arp cache](http://linux-ip.net/html/ether-arp.html)
* [Neighboring subsystem](http://www.linuxfoundation.org/collaborate/workgroups/networking/neighboring_subsystem)
* [rtnetlink](http://man7.org/linux/man-pages/man7/rtnetlink.7.html)
