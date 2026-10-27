#!/usr/bin/env python3
"""Week 6 Task 2 - time every router's table, not just r1's, with sub-second polls.

scenario.sh polls r1 only, once a second, through `docker compose exec` (slow on
Windows). This polls r1, r2 and r3 in parallel with plain `docker exec`, and
records when each table first differs from its pre-event state and when it
reached its final state.

    python3 out/measure_reconverge.py          (from w06-routing/, routers up)

Events, in order (each starts from a converged network):
  1 cut       r1: ip link set eth1 down          (same as scenario.sh cut)
  2 restore   r1: ip link set eth1 up            (same as scenario.sh restore)
  3 silent    r1: iptables drops OSPF on eth1    (link stays up, hellos vanish)
  4 unsilent  r1: iptables rules removed
  5 cost      r1: eth0 ospf cost 10 -> 100       (same as scenario.sh cost)
  6 uncost    r1: eth0 ospf cost 100 -> 10
"""
import re, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

PREFIX = "2026-lecture-network-practice-"
ROUTERS = ["r1", "r2", "r3"]
POOL = ThreadPoolExecutor(len(ROUTERS))


def sh(router, *cmd):
    return subprocess.run(["docker", "exec", PREFIX + router + "-1", *cmd],
                          capture_output=True, text=True).stdout


def table(router):
    out = sh(router, "vtysh", "-c", "show ip route ospf")
    lines = [l for l in out.splitlines() if l.startswith(("O", " "))
             and ("via" in l or "connected" in l)]
    # drop the route age ("00:00:05") so a table only "changes" when a route does
    return tuple(re.sub(r",\s*\d\d:\d\d:\d\d$", "", l).rstrip() for l in lines)


def tables():
    return dict(zip(ROUTERS, POOL.map(table, ROUTERS)))


def wait_stable(quiet=12.0, limit=120):
    """Wait until no table has changed for `quiet` seconds."""
    last, since, t0 = tables(), time.time(), time.time()
    while time.time() - since < quiet and time.time() - t0 < limit:
        time.sleep(0.5)
        now = tables()
        if now != last:
            last, since = now, time.time()
    return last


def event(name, action, watch=90.0, quiet=15.0):
    before = wait_stable()
    t0 = time.time()
    action()
    first, final_at, last = {}, {}, dict(before)
    hist = []
    while True:
        now = tables()
        t = time.time() - t0
        for r in ROUTERS:
            if now[r] != last[r]:
                first.setdefault(r, t)
                final_at[r] = t
                hist.append((t, r, now[r]))
        last = now
        if t > watch or (final_at and t - max(final_at.values()) > quiet):
            break
        if not final_at and t > watch:
            break
    out = [f"## {name}", f"   action at t=0.0 s, polled r1/r2/r3 in parallel"]
    for r in ROUTERS:
        if r in first:
            out.append(f"   {r}: first change {first[r]:5.1f} s, settled {final_at[r]:5.1f} s")
        else:
            out.append(f"   {r}: no change within {watch:.0f} s")
    for t, r, tb in hist:
        out.append(f"   t={t:5.1f}s {r}:")
        out += [f"      {l}" for l in tb]
    text = "\n".join(out)
    print(text, flush=True)
    return text


def main():
    ipt = lambda op: (sh("r1", "iptables", op, "INPUT", "-i", "eth1", "-p", "89", "-j", "DROP"),
                      sh("r1", "iptables", op, "OUTPUT", "-o", "eth1", "-p", "89", "-j", "DROP"))
    cost = lambda c: sh("r1", "vtysh", "-c", "configure terminal", "-c", "interface eth0",
                        "-c", f"ip ospf cost {c}")
    steps = [
        ("1 cut - r1 eth1 admin down", lambda: sh("r1", "ip", "link", "set", "eth1", "down")),
        ("2 restore - r1 eth1 admin up", lambda: sh("r1", "ip", "link", "set", "eth1", "up")),
        ("3 silent failure - drop OSPF on r1 eth1, link stays up", lambda: ipt("-A")),
        ("4 silent repair - remove the drop rules", lambda: ipt("-D")),
        ("5 cost change - r1 eth0 cost 10 -> 100", lambda: cost(100)),
        ("6 cost back - r1 eth0 cost 100 -> 10", lambda: cost(10)),
    ]
    only = sys.argv[1:]
    report = []
    for i, (name, fn) in enumerate(steps, 1):
        if only and str(i) not in only:
            continue
        report.append(event(name, fn))
    with open("out/reconverge-detail.txt", "a", encoding="utf-8") as f:
        f.write(time.strftime("# run %Y-%m-%d %H:%M:%S\n\n") + "\n\n".join(report) + "\n\n")


if __name__ == "__main__":
    main()
