## Part A · The capture (`out/dns.pcapng`)

Taken on my own laptop (Wi-Fi `KT_PASCUCCI_5G`, 172.30.1.67) while running
`python3 task1_resolve.py www.korea.ac.kr` and `www.netflix.com`. The raw capture also held
other applications' lookups; for privacy the file keeps only my resolver's packets
(names under korea.ac.kr / netflix.com / nflxso.net, ISP resolver traffic removed).

- **Why there are unanswered queries first (frames 1–16).** Over UDP, every query to the root
  servers went out and no reply came back on this network — my resolver tried a, b, c root in
  turn (R4) and gave up. Frames 17–26 are my diagnosis (UDP vs. TCP). The resolver was then run
  with DNS over **TCP** (`+tcp`), which this network let through. On the SKT hotspot, UDP worked.
- **A2 · query and its response** — frame **41** (query to 163.152.11.6) and frame **42**
  (response) carry the same transaction ID **0x7261**.
- **A3 · delegation vs. answer** —
  frame **36** is a **delegation**: from root 198.41.0.4, answer count **0**, authority **6** (`NS`
  for `kr.`), additional **11** (glue `A`/`AAAA`).
  frame **42** is an **answer**: from korea.ac.kr's server, answer count **1**
  (`www.korea.ac.kr A 163.152.6.10`), authority 0. Same message format, different sections filled.
- **A4 · largest response** — frame **50**, **905 bytes**: the root's delegation for
  `www.prod.ftl.netflix.com`. It is large because it lists all **13** `.com` gTLD servers in
  AUTHORITY plus **27** glue records (IPv4 and IPv6) in ADDITIONAL.
