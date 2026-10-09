# Week 5 · Task 2 report: where exactly am I on the internet?

Three networks were measured (raw output in `addresses.json`):

| label | where | collected |
|---|---|---|
| `campus wifi (KUWIFI)` | Korea University Sejong, campus Wi-Fi | 2026-09-29 13:1x |
| `phone hotspot` | iPhone personal hotspot on SK Telecom | 2026-09-29 13:29 |
| `cafe wifi (KT_PASCUCCI_5G)` | café Wi-Fi on a KT line (also where the DHCP capture was taken) | 2026-10-10 01:1x |

---

## Part A: campus Wi-Fi (KUWIFI)

### A1. Interface address and mask (from `ipconfig /all`, interface "Wi-Fi", Intel AX211)

| field | value |
|---|---|
| IPv4 address | `172.16.18.128` |
| subnet mask | `255.255.255.0` → **/24** |
| default gateway (first-hop router) | `172.16.18.1` |
| DHCP server | `192.168.98.23` |
| address lease | 13:10:12 → 13:40:11 (**30 minutes**) |
| local DNS server | `163.152.213.9`, `168.126.63.1`, `168.126.63.2` |

The address belongs to the Wi-Fi **interface**, not to the laptop as a whole (§4.3.2). The disconnected
adapters (Bluetooth, VPN) have no IPv4 address at all.

### A2. Subnet range by hand, then checked with Task 1

The subnet is `a.b.c.d/x` with x = 24: a 24-bit network prefix and 32 − 24 = 8 host bits.

```
address   172.16.18.128  = 10101100.00010000.00010010.10000000
mask      255.255.255.0  = 11111111.11111111.11111111.00000000
AND  ->   172.16.18.0    = network prefix
host bits all 1 -> 172.16.18.255 = broadcast
usable    172.16.18.1  ...  172.16.18.254   (256 - 1 network - 1 broadcast = 254 hosts)
```

`network_range("172.16.18.0/24")` from `task1_forward.py` returns
`('172.16.18.1', '172.16.18.254', '172.16.18.255')`, the same as the hand result.

### A3. Default gateway

The gateway `172.16.18.1` is the first usable address, so it is **inside** the range.
It has to be. A subnet is the set of interfaces that can reach each other **without passing through a router**.
The first-hop router is the device that gets me out of that set. My laptop reaches it
directly on the link by finding its MAC address with ARP, so it must have an interface on my subnet. `route print`
shows `172.16.18.0/24` as "on-link" and `0.0.0.0/0 → 172.16.18.1`. A gateway outside the prefix would
itself need a router to reach.

### A4. Public address seen from outside

`api.ipify.org` saw **`163.152.233.18`**. This is inside `163.152.0.0/16`, the block assigned to
Korea University. The campus DNS server `163.152.213.9` is in the same block.

### A5. Private vs public, and how many NATs

- A1 `172.16.18.128` is **private** (RFC 1918 `172.16.0.0/12`). It has meaning only inside the campus network.
- A4 `163.152.233.18` is **public**.
- They differ, so there is **at least one NAT**. It is not carrier-grade NAT, because my address is not in `100.64.0.0/10`.

**Conclusion: one layer of NAT, run by the university.** Evidence from `tracert -d 8.8.8.8`:

```
 1  172.16.0.2         private  (campus router)
 2  192.168.98.132     private  (campus core, same 192.168.98.x network as the DHCP server)
 3  163.152.233.129    PUBLIC, KU's own block, same /24 as my public address .18
 4  175.121.235.141    public, the upstream ISP
 5  10.103.1.142       private (ISP internal link address)
 6  10.222.25.122      private (ISP internal link address)
```

The change from private to public happens between hops 2 and 3, still inside KU. The address the world
sees belongs to KU, not to an ISP, so the translation happens at the campus edge. The later `10.x` hops are
not a second NAT. ISPs often number their internal router links with private addresses, and my datagrams
pass those routers with their source still `163.152.233.18`.

**How to tell one NAT from two:**
1. Find the address on the NAT router's **WAN side**. If it is public and equals what ipify reports,
   there is one NAT. If it is `100.64.x.x` or another private address, a second NAT sits upstream (CGNAT).
2. Look up who owns the public address. If it is your own organisation's block, the NAT is yours.
   If it is a block from an ISP's shared pool, that suggests CGNAT.
3. In traceroute, find where private turns public, and who owns that hop.

The café network (Part B) shows check 1 directly.

---

## Part B: comparing networks

| | campus wifi (KUWIFI) | phone hotspot (iPhone, SKT) | café wifi (KT) |
|---|---|---|---|
| private address | `172.16.18.128` | `172.20.10.2` | `172.30.1.2` |
| mask | 255.255.255.0 (**/24**) | 255.255.255.240 (**/28**) | 255.255.255.0 (**/24**) |
| usable range | .1 – .254, bcast .255 | `172.20.10.1` – `.14`, bcast `.15` | `172.30.1.1` – `.254`, bcast `.255` |
| first-hop router | `172.16.18.1` | `172.20.10.1` | `172.30.1.254` |
| DHCP server | `192.168.98.23` (other subnet → relay) | `172.20.10.1` (the phone) | `172.30.1.254` (the café router) |
| lease | 30 min | 1 hour | 1 hour |
| public IPv4 | `163.152.233.18` (Korea University) | `223.39.217.232` (AS9644 SK Telecom) | `210.91.221.32` (AS4766 Korea Telecom) |
| public IPv6 | none | `2001:2d8:6341:821b:…/64` (SKT) | none |
| NAT layers | 1 (KU edge) | ≥ 1, likely 2 | **1** (café router) |

The ranges were computed as in A2 and checked with `network_range`. For the hotspot the mask
`255.255.255.240` leaves 4 host bits, which gives 16 addresses (`.0` – `.15`, 14 usable). `route print` there also lists
`172.20.10.15` as the broadcast. Every first-hop router is inside its own range. The café router uses the
*last* usable address `.254`, while campus and the iPhone use the first, `.1`. Both are fine.

### B3. What changed and why

**Every network gave a different private address and a different public address, for different reasons.**

- **The private address changes** because a different DHCP server hands it out, and a private address only
  has meaning inside its own network. All three are in `172.16.0.0/12`, but `172.16.18.0/24`,
  `172.20.10.0/28` and `172.30.1.0/24` are unrelated networks that happen to reuse the same private
  block. That reuse is exactly what lets many networks share private addresses without conflict.
  The iPhone uses a **/28** because a hotspot serves only a handful of devices.
- **The public address changes** because the traffic leaves through a different organisation each time:
  KU's block, SKT's block, KT's block. The public address belongs to whoever runs the **last NAT**, not to my
  laptop.
- **Café = one NAT, cleanly.** The café router is first-hop router, DHCP server, and NAT at once
  (`172.30.1.254`). This is the NAT-enabled router of §4.3.3: it gets one address from the ISP and runs a
  DHCP server for the private side. Traceroute hop 2 is `210.91.221.1`, in the **same /24 as the public
  address `210.91.221.32`**. So the router's WAN side holds that public address itself, and there is no second NAT
  behind it.
- **Hotspot = at least one NAT, very likely two.** The iPhone does NAT (`172.20.10.2` → its cellular
  address). I cannot see the phone's cellular IPv4 from the laptop. If SKT gives the phone a private or
  `100.64.x` address, as is usual for mobile IPv4, then `223.39.217.232` is a carrier NAT shared by many
  subscribers.
- **What did not change.** The Wi-Fi interface's **MAC address `E8-C8-29-2C-24-A0`** was the same on all three.
  It is burned into the network card and identifies the interface on the link, while the IP address is lent
  by whichever network the interface joins. Also unchanged: every network gave the address **by DHCP**, every
  private address was RFC 1918, and every network had **at least one NAT** between me and the outside. That is the
  normal setup for a client today, because a client does not need a fixed or public address.
- **IPv6.** Only the hotspot gave the laptop **global IPv6 addresses** (`2001:2d8:…`, SKT's prefix), next to
  IPv4. This is a **dual-stack** host. Those IPv6 addresses are not translated: each device gets its own globally
  reachable address, which is the assumption NAT broke for IPv4.

---

## Part C: DHCP, my own capture (`dhcp.pcapng`)

Taken on the café Wi-Fi (`KT_PASCUCCI_5G`) on 2026-10-10 at 01:17:58, with the capture filter `port 67 or port 68`.
I ran `ipconfig /release` then `ipconfig /renew`. Releasing first makes the client start over from Discover,
so the capture holds the full four-step exchange instead of only Request/ACK. The file has only these 5 DHCP packets.

### C1. The messages

| # | t | message | IP src → dst | Ethernet dst | transaction ID |
|---|---|---|---|---|---|
| 1 | 0.000 s | Release | `172.30.1.2:68 → 172.30.1.254:67` | router MAC | `0x3c51cb61` |
| 2 | 2.937 s | **Discover** | `0.0.0.0:68 → 255.255.255.255:67` | `ff:ff:ff:ff:ff:ff` | `0x7a0085e7` |
| 3 | 3.031 s | **Offer** (yiaddr `172.30.1.2`) | `172.30.1.254:67 → 172.30.1.2:68` | my MAC | `0x7a0085e7` |
| 4 | 3.034 s | **Request** (requested IP `172.30.1.2`, server id `172.30.1.254`) | `0.0.0.0:68 → 255.255.255.255:67` | `ff:ff:ff:ff:ff:ff` | `0x7a0085e7` |
| 5 | 3.051 s | **ACK** | `172.30.1.254:67 → 172.30.1.2:68` | my MAC | `0x7a0085e7` |

The whole Discover → ACK exchange took **114 ms**. Offer and ACK carry what DHCP delivers besides the
address: mask `255.255.255.0`, router `172.30.1.254`, DNS `168.126.63.1`, `168.126.63.2` (KT).

### C2. Discover source and destination

- Source: **`0.0.0.0`**. The client has no IP address yet, and asking for one is the whole point of the
  message.
- Destination: **`255.255.255.255`**, the broadcast address, sent to UDP port 67. This is forced by the source:
  the client does not know the server's address, its own subnet, or its first-hop router. The only destination it can
  use is "everyone on this link". The Ethernet frame goes to `ff:ff:ff:ff:ff:ff` for the same reason.
- The server cannot reply to `0.0.0.0`. It tells clients apart by their **MAC address** (`chaddr`) and the
  **transaction ID**. All four messages share `0x7a0085e7`, and the Release before them used a different one.
- Not required, but worth noting: the Discover already contained option 50, *requested IP = `172.30.1.2`*. The client
  remembered its previous address and asked for it back, and the server agreed. That is why my address did not change.
  Campus Wi-Fi did the same when I reconnected on 9/29.

### C3. Lease time

- The server offered an address lease time of **3,600 s = 1 hour**. The laptop's lease record agrees
  (obtained 01:06:01 → expires 02:06:01 before the renew).
- The server sent no T1/T2 options, so the client uses the RFC 2131 defaults. At **half the lease (T1 = 30 min)**
  it unicasts a Request straight to `172.30.1.254` to renew, with no Discover and no broadcast. At T2 = 87.5 % (52.5 min)
  it broadcasts a Request to any server (rebinding). When the lease expires it must stop using the address
  and start again from Discover.
- Comparison: campus gives only **30 min**, and the official Kurose–Ross trace gives **24 h**. A campus has
  many more devices coming and going than a café or a home, so a short lease lets it **reclaim addresses from
  departed devices** sooner. The campus DHCP server `192.168.98.23` is not on my /24, which means the campus
  router acts as a **DHCP relay agent**.

### C4. Discover is broadcast, but Offer/ACK are unicast. Why?

Between Discover and Offer, the **server learned two things**: the client's MAC address (from the Discover)
and the address it is about to give (`yiaddr` = `172.30.1.2`). So it can send the Ethernet frame straight to my
MAC and put the new address as the IP destination. It needs no ARP for this, because it already knows the MAC.
This is allowed because the client left the **broadcast flag = 0** in every message, which means "I can accept a unicast
before my address is configured". A client that cannot do this sets the flag to 1, and then Offer/ACK are broadcast too.
That is the case the textbook describes when it says the offer is "also broadcast" (lecture p. 260).

The **Request is still broadcast** (`0.0.0.0 → 255.255.255.255`) even though the client now knows the
server. The client has no configured address until the ACK arrives, and the broadcast tells *every* server that made an
offer which one was chosen (server id `172.30.1.254`). The Release in frame 1, sent while the client still held
its address, is a plain unicast `172.30.1.2 → 172.30.1.254`.

### For comparison: the official trace

`traces/dhcp-wireshark-trace1-1.pcapng` (Kurose–Ross 9e) shows the same pattern: Discover/Request
`0.0.0.0 → 255.255.255.255`, Offer/ACK unicast to `192.168.86.65`, broadcast flag 0. It also differs in a few ways:
the server granted 24 h with explicit T1 = 12 h and T2 = 21 h, and the client retransmitted its Discover after
1.6 s before an Offer arrived.

> Wireshark lab trace files from J.F. Kurose and K.W. Ross,
> *Computer Networking: A Top-Down Approach*, 9th ed.
> <https://gaia.cs.umass.edu/kurose_ross/>
> Copyright 1996-2025 J.F. Kurose, K.W. Ross. All Rights Reserved.
