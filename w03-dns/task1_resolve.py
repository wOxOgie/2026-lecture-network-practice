#!/usr/bin/env python3
"""Week 3 · Task 1 — Build your own iterative resolver.

Textbook §2.4.2 - §2.4.3.

`dig +trace` walks root -> TLD -> authoritative for you. In this task you do
that walk yourself: start at a root server, read the delegation it returns,
ask the next server, and keep going until somebody answers authoritatively.

You may shell out to `dig` for the transport, or use a DNS library
(`dnspython` is in the container). Either is fine - what matters is that
*you* follow the delegations rather than letting a tool do it.

    python3 task1_resolve.py www.korea.ac.kr
    python3 task1_resolve.py --verify        # check yourself against dig

Pass condition
--------------
`--verify` resolves five names with your resolver and with `dig`, and the
addresses must agree. A name behind a CDN may legitimately return a different
address each time; the harness compares the *set of authoritative nameservers*
you ended at for those, not the address.
"""
import argparse, os, subprocess, sys

# Root servers. Everything starts here; there is no earlier step.
ROOT_SERVERS = [
    "198.41.0.4",       # a.root-servers.net
    "199.9.14.201",     # b.root-servers.net
    "192.33.4.12",      # c.root-servers.net
]

# (name, kind).  "stable" names must match dig exactly.  "cdn" names are served
# from many replicas and may legitimately give you a different address than dig
# got a second earlier - for those we only require that you reached an answer.
VERIFY_NAMES = [
    ("www.korea.ac.kr", "stable"),
    ("dns.google", "stable"),
    ("en.wikipedia.org", "stable"),
    ("www.stanford.edu", "stable"),
    ("www.microsoft.com", "cdn"),
]


class Resolver:
    """Your iterative resolver.

    The whole point is that you never ask a server to recurse for you.
    You ask one server, it says "not mine, ask over there", and you go there.

    Suggested shape - but it is yours to design:

        resolve(name) -> (address, path)
            address : the A record you ended up with, as a string
            path    : the servers you asked, in order, so you can show your work

    Things you will hit, in roughly this order:

    1.  A delegation gives you NS *names*, sometimes with glue A records and
        sometimes without. No glue means you have to resolve that nameserver's
        name first - which is another walk. Decide what you do there.
    2.  A server may not answer. Try the next one rather than giving up.
    3.  CNAMEs. The answer you get back may be a different name than the one
        you asked for, and you have to start again with that name.
    4.  Loops. Cap your depth.

    If you shell out to dig, the flag you want is `+norecurse`, so that the
    server you ask replies with a delegation instead of doing the work:

        dig @198.41.0.4 www.korea.ac.kr +norecurse
    """

    MAX_DEPTH = 4        # nested walks for glue-less nameservers (R3, R6)
    MAX_STEPS = 20       # referrals followed in one walk (R6)
    MAX_CNAMES = 8       # CNAME restarts in one walk (R5, R6)

    def __init__(self):
        self.glueless = 0    # how many extra walks a missing glue cost us

    def query(self, server, name):
        """One non-recursive question to one server.

        Returns {"answer": [...], "authority": [...], "additional": [...]}
        where each record is (owner, type, data), or None if the server did
        not answer.
        """
        args = ["dig", f"@{server}", name, "A", "+norecurse",
                "+time=2", "+tries=1", "+nocmd", "+nostats", "+noquestion"]
        if os.environ.get("DIG_TCP"):        # for networks where UDP/53 is broken
            args.append("+tcp")
        r = subprocess.run(args, capture_output=True, text=True)
        if r.returncode != 0 or "status: NOERROR" not in r.stdout:
            if "status: NXDOMAIN" in r.stdout:
                raise LookupError(f"{name}: NXDOMAIN from {server}")
            return None
        sections = {"answer": [], "authority": [], "additional": []}
        current = None
        for line in r.stdout.splitlines():
            if line.startswith(";; ANSWER SECTION"):
                current = "answer"
            elif line.startswith(";; AUTHORITY SECTION"):
                current = "authority"
            elif line.startswith(";; ADDITIONAL SECTION"):
                current = "additional"
            elif line.startswith(";") or not line.strip():
                continue
            elif current:
                f = line.split()
                # owner  ttl  IN  type  data...
                if len(f) >= 5:
                    sections[current].append(
                        (f[0].rstrip(".").lower(), f[3], f[4].rstrip(".").lower()))
        return sections

    def resolve(self, name, depth=0):
        if depth > self.MAX_DEPTH:
            raise RecursionError(f"glue-less chain deeper than {self.MAX_DEPTH}")
        qname = name.rstrip(".").lower()
        servers = list(ROOT_SERVERS)            # R2: always start at the root
        path, cnames, indent = [], 0, "    " * depth

        for _ in range(self.MAX_STEPS):
            # R4: try each server until one answers
            for server in servers:
                resp = self.query(server, qname)
                if resp is not None:
                    break
            else:
                raise TimeoutError(f"no server answered for {qname}: {servers}")
            path.append(f"{indent}{server}  ({qname})")

            # 1. An answer for the name we asked?
            a = [d for o, t, d in resp["answer"] if o == qname and t == "A"]
            if a:
                return a[0], path
            cname = [d for o, t, d in resp["answer"] if o == qname and t == "CNAME"]
            if cname:                           # R5: start over with the new name
                cnames += 1
                if cnames > self.MAX_CNAMES:
                    raise RecursionError(f"more than {self.MAX_CNAMES} CNAMEs")
                qname, servers = cname[0], list(ROOT_SERVERS)
                continue

            # 2. Otherwise it must be a delegation: NS names in authority
            ns_names = [d for o, t, d in resp["authority"] if t == "NS"]
            if not ns_names:
                raise LookupError(f"{qname}: no answer and no delegation from {server}")
            glue = [d for o, t, d in resp["additional"]
                    if t == "A" and o in ns_names]
            if glue:
                servers = glue
                continue

            # 3. R3: delegation without glue - resolve a nameserver's name first
            for ns in ns_names:
                self.glueless += 1
                try:
                    ns_addr, sub_path = self.resolve(ns, depth + 1)
                except (LookupError, TimeoutError):
                    continue
                path.extend(sub_path)
                servers = [ns_addr]
                break
            else:
                raise LookupError(f"could not resolve any NS of {qname}: {ns_names}")

        raise RecursionError(f"more than {self.MAX_STEPS} referrals for {name}")


# ------------------------------------------------------------------- harness
def dig_answer(name):
    """What the system resolver says, for comparison."""
    out = subprocess.run(["dig", "+short", name, "A"],
                         capture_output=True, text=True).stdout
    return [l for l in out.split() if l and l[0].isdigit()]


def verify():
    r, failures = Resolver(), 0
    for name, kind in VERIFY_NAMES:
        try:
            addr, path = r.resolve(name)
        except NotImplementedError:
            print("Nothing implemented yet - write Resolver.resolve first.")
            return 1
        except Exception as e:
            print(f"  FAIL  {name:<22} your resolver raised {e!r}")
            failures += 1
            continue
        expected = dig_answer(name)
        if addr in expected:
            note = ""
        elif kind == "cdn":
            note = "  <- differs, but this name is CDN-hosted. Explain it."
        else:
            note = "  <- should have matched"
            failures += 1
        print(f"  {'FAIL' if note.endswith('matched') else 'ok  '}  {name:<22} "
              f"you={addr:<16} dig={','.join(expected) or '-'}   "
              f"hops={len(path)}{note}")
    print(f"\n  {len(VERIFY_NAMES) - failures}/{len(VERIFY_NAMES)} ok")
    return 1 if failures else 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("name", nargs="?", default="www.korea.ac.kr")
    p.add_argument("--verify", action="store_true")
    a = p.parse_args()

    if a.verify:
        sys.exit(verify())

    r = Resolver()
    addr, path = r.resolve(a.name)
    for i, server in enumerate(path, 1):
        print(f"  {i}. asked {server}")
    print(f"\n  {a.name} -> {addr}")
    print(f"  glue-less nameserver lookups: {r.glueless}")


if __name__ == "__main__":
    main()
