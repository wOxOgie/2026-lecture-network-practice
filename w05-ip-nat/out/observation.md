# Week 5 · Observation

## Task 1 · Subnets and longest-prefix match
- /32 → `(a, a, a)`: a host route, one address. /31 → `(first, second, None)` per RFC 3021: point-to-point, both usable, no broadcast. "Network + 1 … broadcast − 1" would be empty or reversed for both. /30 is ordinary (`10.0.0.4/30` → .5, .6, .7).
- 10.20.30.70 is inside `10.0.0.0/8`, `10.20.0.0/16`, `10.20.30.0/24`, `10.20.30.64/26` (and `0.0.0.0/0`). Longest prefix match picks /26 → lab-rack-2: the longer prefix is the more specific route, carving one network out of the aggregate.
- Equal length + different next hop can only be the same prefix twice (two different /n blocks never overlap). Table keyed by (network, length); the later `add` replaces the earlier, like a router installing a newer route.

## Task 2 · Where am I?
- Campus: `172.16.18.128/24` → `163.152.233.18` (KU's own /16), private → public between hop 2 `192.168.98.132` and hop 3 `163.152.233.129` = one NAT at the campus edge. Café: router `172.30.1.254` is first-hop router + DHCP server + NAT, hop 2 `210.91.221.1` is in the same /24 as the public `210.91.221.32` (KT) = one NAT. iPhone hotspot: ≥ 1 NAT (the phone), likely 2 (carrier).
- Campus, hotspot (`172.20.10.2/28` → `223.39.217.232`, SKT), café (`172.30.1.2/24` → `210.91.221.32`, KT): both addresses changed every time. Private = a different DHCP server, meaningful only inside its network; public = a different organisation runs the last NAT. Unchanged: MAC `E8-C8-29-2C-24-A0` (hardware, not lent by the network), and the pattern DHCP + RFC 1918 + ≥ 1 NAT. Only the hotspot also gave global IPv6 (dual stack, no NAT).
- Own capture (café): Discover `0.0.0.0 → 255.255.255.255`. No address yet, so it can only broadcast; the server matches the client by MAC and transaction ID `0x7a0085e7`. Offer/ACK unicast to `172.30.1.2` (broadcast flag 0). Lease 1 h (renew at T1 = 30 min); campus 30 min via a relay, official trace 24 h.

## Task 3 · Fast LPM
- One dict per prefix length (keyed by `network >> (32 − len)`), probed longest first, first hit wins. 364 KiB vs 353 KiB for the list, 1,722× faster, 0 of 20,000 answers differ.
- R5: lookup work ∝ number of distinct prefix lengths (7 here, ≤ 33), one shift + one hash per probe, independent of route count.
- Python: a dict lookup is one C call vs up to 32 interpreted trie steps. Hardware forwards on a nanosecond scale (10 Gbps, 64 B → 51.2 ns per datagram) and needs a fixed worst case with no collisions or resizing, pipelined one bit-level per stage. A trie or TCAM gives that, bounded by the 32-bit width.
