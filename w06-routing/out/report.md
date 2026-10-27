# Week 6 · Report (full notes behind observation.md)

## Task 1: link state by hand

- **Tie-break rule:** my heap holds `(cost, first_hop, node)`. When two shortest paths tie, the one that
  leaves by the alphabetically smallest neighbour is settled first and wins. The rule is deterministic,
  so the table is the same on every run. A real OSPF router does not pick one path. It installs **all**
  equal-cost next hops (ECMP, up to `maximum-paths`) and hashes each flow onto one of them. I saw this in
  Task 2: r1 listed `172.20.0.0/16` with two `via` lines.
- **u → w goes to x, not w:** the direct link `u-w` costs 5, but `u-x-y-w` costs 1+1+1 = **3**. The table
  stores only the first hop (`x`) and trusts x and y to do the rest. Sending w traffic out the w interface
  would be adjacency, not routing.
- **After u-x fails:** the costs become v 2, x 4, w 5, y 5, z 7, and **every destination except v** changed
  its hop to v. v was already reached directly. For w there is a tie (direct 5 vs u-v-w 5), and my
  rule picked `v`. A real router would split the traffic over both.

## Task 2: break a real network

Setup notes: `frrouting/frr:v9.1.0` does not exist on Docker Hub, so I pulled `quay.io/frrouting/frr:9.1.0`
and re-tagged it. On Windows, git checks out `topology/*` with CRLF line endings, and ospfd would not start
(`getaddrinfo failed` on `127.0.0.1\r`). I converted the files to LF.

- **A2:** the domestic path (www.snu.ac.kr) leaves KU after **hop 3, `163.152.233.129`**, which is the last
  address in KU's `163.152.0.0/16`. Hop 4, `175.121.235.141`, belongs to **SK Broadband** (APNIC RDAP).
  After that come SKB's internal `10.x` core and `211.108.22.106` (SKB), then SNU's `147.46.254.187`.
  (www.korea.ac.kr is KU Anam and stays inside `163.152/16`, so it never leaves the campus network.)
- **A3:** on the path to www.washington.edu, hop 7 (`10.222.38.147`) answers in 4–12 ms and hop 8
  (`10.222.3.79`) in 121–359 ms. Hop 9 is `pnwgp-six1.pnw-gigapop.net`, the **Seattle** Internet Exchange,
  at ~125 ms. That single +115 ms jump is the trans-Pacific cable from Korea to the US Pacific Northwest.
  NCP (Busan → Oregon) fits, but the hostname only names Seattle, so the exact cable is my guess.
- **A4:** for `1.1.1.1`, the last hop that answered is hop 12, `141.101.82.19` (Cloudflare), at ~8–39 ms,
  right after Dreamline's Korean routers. About 12 hops and ~10 ms means the replica is **in Korea**,
  not in Australia or the US. Anycast lets BGP deliver the same address to the nearest site.
- **A5:** `* * *` has two different causes. (1) **A router on the path** does not send ICMP Time Exceeded,
  or rate-limits it. Hops 3–5 showed `*` when I ran 11 traceroutes in parallel but answered when I ran
  them one at a time, so that was rate limiting. Forwarding still works. (2) **The destination or its
  firewall** drops the probe or the reply. www.snu.ac.kr, www.washington.edu, and 1.1.1.1 all go silent
  at the end, even though the site loads, so the end host is filtering ICMP. In the first case the
  path is fine and only the reporting fails. In the second, the trace never reaches the end.
- **B2:** each router learned exactly one network it has no interface on. r1 learned `172.20/16` (r2–r3),
  r2 learned `172.19/16`, and r3 learned `172.18/16`. Each route costs 20 and uses **two** next hops
  (ECMP), because both ways around the triangle cost 10+10.
- **B4:** `scenario.sh cut` reported **3 s**. With parallel 0.5 s polling, all three tables changed within
  **≤0.5 s**. That is **not** the 40 s dead interval. `ip link set eth1 down` is a local link-down event,
  so r1 knows immediately, re-originates its router-LSA, and floods it via r3. r2 removed the r1 path
  before its own dead timer expired. To check the timers (Hello 10 s / Dead 40 s, FRR defaults, not
  written in `frr.conf`), I also made a **silent** failure: iptables dropped OSPF on r1 eth1 while the
  link stayed up. That took **36.9–38.0 s**, which fits the 40 s dead interval minus up to 10 s since the last
  hello.
- **B5:** coming back took **9.4 s (r1) / 14.8 s (r2)** after admin-up, and **2.8 / 12.1 s** after the silent
  repair. Going down took 0.5 s (link down) or 37 s (silent). The two directions use different
  mechanisms. A dead neighbour is noticed either by a local link event (instant) or by **absence** of
  hellos, which can only be detected by waiting out the dead interval. A new neighbour has to **build**
  an adjacency: hellos in both directions (up to one 10 s hello interval), 2-Way, DR/BDR, database
  exchange, and Full. Only after that does SPF use the link. r3 was the exception at 0.5 s: it only needed r1's stub network `172.18/16` back, and that needs no adjacency.
- **C3:** raising r1 eth0's cost from 10 to 100 moved the traffic in **≤0.5 s**, and so did lowering it
  back. r1 now reaches `172.20/16` only via r2, and r2 reaches `172.19/16` only via r3. No link went down.
  (Before: `route-before.txt`. After: `reconverge-detail.txt`, event 5.) This is faster than B4/B5
  because nothing has to be *detected*. The router whose configuration changed re-originates its LSA
  at once, and flooding plus SPF take milliseconds. A failure first has to be *noticed*, and a
  silent one only through the 40 s dead timer.

## Task 3: reconverge without recomputing the world

- **What I keep:** the cost vector `dist` (one int per router, about 13 KB for 400 routers, the same size as
  the table) in addition to the graph and table that the baseline already keeps. A full recompute
  runs `dijkstra_table()`, which is counted, and also gets the cost vector in the same step, because the
  reference SPF throws costs away.
- **Key fact:** `dijkstra_table` settles nodes in (cost, name) order. So a node's hop is inherited from
  its **first tight predecessor** (`d[p] + w == d[v]`) in that order. If the distances and the set of tight
  links do not change, the table cannot change. My incremental updates reproduce this rule exactly.
- **The three cases:** (1) down/dearer on a link that is not tight → skip. If it was tight but the far
  end has another equally short predecessor, no distance moves; I only re-derive that node's hop and
  its successors. (2) up/cheaper with `d[a]+w > d[b]` both ways → skip. (3) up/cheaper that is
  shorter or equal → push the new shorter costs outward (only improving nodes are touched) and re-derive
  hops locally. **What still forces a full SPF:** a failure or cost increase on the *only* shortest way
  into a node, because then distances grow. That was 176 of 1000 events (78 downs, 98 cost increases).
- **Result:** **177 SPF runs instead of 1001 → 82% avoided (strong)**. The table was correct after all 1000
  events, and also on seeds 1, 2, 3, 7, and 99 (0 wrong).
- **R5:** wall time is 3.0 s vs 1.7 s for the baseline. In Python, every comparison and dict lookup in my
  bookkeeping costs about as much as a step of Dijkstra, and a recompute also runs the extra cost
  pass. It is still the right choice on a router. The scarce resource there is **control-plane
  CPU**, shared with hello timers, LSA flooding, and BGP. A full SPF scales with the size of the whole area,
  and a flapping link triggers one on every router at once. If a router is busy with SPF, it can miss
  hellos and drop neighbours that are fine, and every recompute can also rewrite hardware FIB entries. In C, the bookkeeping
  is a few memory reads, and touching only the affected part of the tree keeps CPU use flat while links
  flap. Real OSPF does this as incremental SPF and partial route calculation.
