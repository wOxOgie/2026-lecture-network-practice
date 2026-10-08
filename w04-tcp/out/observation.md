# Week 4 · Observation

## Task 1 · Reliable delivery
- Selective repeat (window 16, per-packet timer, receiver buffer; costs receiver state). Reordering forced it: a receiver that drops out-of-order packets needed 1,346 packets instead of 597; stop-and-wait needed 522 steps instead of 78.
- 2,000 bytes = 250 data packets minimum. Sent 311 data + 286 ACKs = 597 (1.24× data, 1.19× overall); the extra is retransmission of lost data and lost ACKs.
- Duplication broke first: writing every arrival corrupted the output, and not ACKing duplicates caused a livelock (lost ACK → endless retransmission). Fix: ACK every copy, write each sequence number once.

## Task 2 · Handshake and throughput
- Capture: café Wi-Fi, port 50744, frames 1 (SYN), 2 (SYN-ACK), 3 (ACK). ISNs: client 1,051,786,843, server 1,422,020,476. Random, not 0, so old delayed segments do not fit a new connection and attackers cannot guess them.
- SYN: MSS 1460, window scale 8 (×256), SACK permitted. Scaled rwnd 524,032 B; bytes in flight averaged ≈195 KB, BDP ≈ 75 Mb/s × 9 ms ≈ 85 KB. In-flight is capped by min(cwnd, rwnd); rwnd was reached only once, so cwnd (kept near the bottleneck rate) was the limit.
- Wi-Fi median 75.45 Mb/s (spread 29%: only run 1 was slow, TTFB 212 ms vs. ~70 ms, cold DNS/TLS/edge), handshake 9.7 ms; hotspot median 19.41 Mb/s (spread 239%, varying radio and cell load), handshake 46.1 ms (≈52 ms without a 0.0 ms run caused by slow DNS). Longer RTT → lower throughput (161 ms → 6.1 Mb/s, 29 ms → 52.5 Mb/s): §3.7 slow start with self-clocking: cwnd grows only as ACKs return (doubling once per RTT), and rate ≈ cwnd / RTT.

## Task 3 · Congestion control
- R5: baseline goodput 986.8 vs. mine 948.5, but it keeps the queue at 8.8/10 and loses 37.4% (2,340 retx). Every flow sharing the link waits and loses packets: the §3.6 costs of congestion (queuing delay, capacity wasted on dropped packets). Mine: 96% of it, loss 2.0%, queue 4.3.
- Loss starts at window ≈ 31 (pipe 20 + queue 10 + 1). Cut to 0.6 × 31 ≈ 19 ≈ pipe; AIMD sawtooth 19 → 31. Growth 0.5/RTT, one cut per window, because one overflow times out a burst of packets. The textbook resets cwnd to 1 MSS on timeout; I cut to 0.6 to keep the pipe full but the queue short.
- Gentler backoff: β 0.5 → 86% (queue 3.1), 0.7 → 97% (4.6), 0.85 → 99% but loss 5.1%, queue 7.2 (fails). Textbook-style: reset to 1 MSS on timeout = 81%, halving on every loss = 82%.
