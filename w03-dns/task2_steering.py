#!/usr/bin/env python3
"""Week 3 · Task 2 — Does DNS actually steer you? Measure it.

Textbook §2.4.3 (records) and §2.5 (CDNs).

The lecture claims two things:

    (a) most large sites are served by a CDN, reached through a CNAME chain
    (b) DNS steers each user to a *nearby* replica

Both are testable from your laptop, and one of them is harder to prove than
the slide makes it look. Your job is to produce the evidence and a number.

    python3 task2_steering.py --collect        # gather the raw data
    python3 task2_steering.py --report         # your analysis

What you have to build
----------------------
1.  For each hostname in SITES, follow the CNAME chain to its end and record
    every hop. `--collect` should leave the raw data in out/chains.json.

2.  Decide, for each site, whether it is served by a **third party**.
    This is the hard part and there is no single right answer:

      - `www.microsoft.com` ends at `akamaiedge.net`     - clearly third party
      - `www.netflix.com`   stops inside `netflix.com`   - own CDN, not third party
      - some sites have no CNAME at all and still sit behind a CDN (anycast)
      - `foo.cloudfront.net` and `foo.s3.amazonaws.com` are both Amazon,
        but they are not the same service

    Write down the rule you used and **defend it in observation.md**. A rule
    that just compares the last two labels will be wrong on at least one of
    the sites below; find which, and say so.

3.  Ask **two different resolvers** for the same name and compare the
    addresses you get back. If DNS really steers by location, a CDN-hosted
    name should answer differently to resolvers sitting in different places.

        RESOLVERS below has your system resolver and two public ones.

    Report: of N CDN-hosted sites, how many returned a different address set
    from a different resolver? Claim (b) predicts most of them. Check it.

Pass condition
--------------
There is no fixed answer. You pass by producing, in out/report.md:

  - the table: site | chain length | final zone | third party? | your rule's verdict
  - the steering number: "X of N sites answered differently to a different resolver"
  - at least one site where your classification rule was wrong, and why
"""
import argparse, json, os, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

SITES = [
    "www.microsoft.com",     # Akamai, multi-hop
    "www.netflix.com",       # own CDN
    "www.adobe.com",
    "www.cnn.com",
    "www.apple.com",
    "www.korea.ac.kr",       # no CDN at all
    "www.stanford.edu",
    "www.bbc.co.uk",
    "www.spotify.com",
    "www.github.com",
    "www.wikipedia.org",
    "www.nytimes.com",
]

RESOLVERS = {
    "system": None,          # whatever is in your resolv.conf
    "google": "8.8.8.8",
    "quad9":  "9.9.9.9",
}


def dig(name, rtype="A", server=None):
    """Raw lookup. Transport only - the thinking is yours."""
    args = ["dig", "+short", name, rtype]
    if server:
        args.insert(1, f"@{server}")
    if os.environ.get("DIG_TCP"):            # for networks where UDP/53 is broken
        args.append("+tcp")
    out = subprocess.run(args, capture_output=True, text=True).stdout
    return [l.strip() for l in out.splitlines() if l.strip()]


CHAINS = os.path.join(OUT, "chains.json")
MAX_CHAIN = 10
REPEATS = 2              # ask each resolver twice so round-robin is visible


def follow_chain(name, server=None):
    """[name, cname1, cname2, ...] - every hop until there is no CNAME."""
    chain = [name]
    while len(chain) <= MAX_CHAIN:
        nxt = dig(chain[-1], "CNAME", server)
        if not nxt:
            break
        chain.append(nxt[0].rstrip(".").lower())
    return chain


def a_records(name, server):
    ips = set()
    for _ in range(REPEATS):
        ips.update(l for l in dig(name, "A", server) if l[0].isdigit())
    return sorted(ips)


def collect(network):
    """Gather raw chains and per-resolver answers into out/chains.json.

    Results are kept per network label, so running it again on a second
    network adds to the file instead of replacing it (B3).
    """
    data = json.load(open(CHAINS, encoding="utf-8")) if os.path.exists(CHAINS) else {}
    for site in SITES:
        chain = follow_chain(site)
        answers = {label: a_records(site, server) for label, server in RESOLVERS.items()}
        first = next((ip for ips in answers.values() for ip in ips), None)
        ptr = dig(first, "PTR") if first else []
        entry = data.setdefault(site, {"chain": chain, "answers": {}, "ptr": {}})
        entry["chain"] = chain
        entry["answers"][network] = answers
        entry["ptr"][network] = {first: ptr[0].rstrip(".") if ptr else None} if first else {}
        print(f"  {site:<20} chain={len(chain) - 1}  final={chain[-1]}")
        for label, ips in answers.items():
            print(f"      {label:<7} {', '.join(ips) or '-'}")
    with open(CHAINS, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n  saved {CHAINS}  (network = {network})")


# Second-level public suffixes that appear in SITES or their chains.  Without
# these, "the last two labels" of www.bbc.co.uk would be "co.uk".
TWO_LEVEL_SUFFIXES = {"co.uk", "ac.kr", "co.kr", "or.kr", "go.kr"}

# Ground truth, checked by hand (who owns the final zone, and does a CDN
# sit in front of the site).  The rule below does NOT see this table; it
# is only used to grade the rule.
TRUTH = {
    "www.microsoft.com": ("third party", "Akamai (akamaiedge.net)"),
    "www.netflix.com":   ("own CDN",     "Netflix Open Connect, own zone"),
    "www.adobe.com":     ("third party", "Akamai (akamai.net)"),
    "www.cnn.com":       ("third party", "Fastly"),
    "www.apple.com":     ("third party", "Akamai (edgekey -> akamaiedge)"),
    "www.korea.ac.kr":   ("no CDN",      "university server, one address"),
    "www.stanford.edu":  ("third party", "Netlify, fronted by AWS Global Accelerator anycast"),
    "www.bbc.co.uk":     ("third party", "Fastly"),
    "www.spotify.com":   ("third party", "Fastly"),
    "www.github.com":    ("own",         "GitHub's own servers (Microsoft/Azure address space)"),
    "www.wikipedia.org": ("own CDN",     "Wikimedia Foundation runs its own caching sites; wikimedia.org is the same owner"),
    "www.nytimes.com":   ("third party", "Fastly (via nyt.net)"),
}


def registrable(name):
    """example: a.b.bbc.co.uk -> bbc.co.uk, x.akamaiedge.net -> akamaiedge.net"""
    labels = name.rstrip(".").lower().split(".")
    n = 3 if ".".join(labels[-2:]) in TWO_LEVEL_SUFFIXES else 2
    return ".".join(labels[-n:])


def rule(site, chain):
    """My rule: third party if the chain ends in a different registrable
    domain (public-suffix aware) than the site itself."""
    return "third party" if registrable(chain[-1]) != registrable(site) else "first party"


def prefixes(ips):
    return {".".join(ip.split(".")[:3]) for ip in ips}


def report():
    """Read out/chains.json and produce out/report.md."""
    data = json.load(open(CHAINS, encoding="utf-8"))
    networks = sorted({n for e in data.values() for n in e["answers"]})
    L = ["# Week 3 · Task 2 report", "",
         f"Networks measured: {', '.join(networks)}  ",
         f"Resolvers: " + ", ".join(f"{k} ({v or 'system resolver of that network'})"
                                    for k, v in RESOLVERS.items()), "",
         "## B4 · Who serves each site", "",
         "**Rule** — a site is served by a *third party* if its CNAME chain ends in a "
         "different registrable domain than the site's own (`www.bbc.co.uk` → `bbc.co.uk`, "
         "public-suffix aware for `co.uk`/`ac.kr`). Ground truth was checked by hand.", "",
         "| site | chain length | final zone | third party? (truth) | rule's verdict | match |",
         "|---|---|---|---|---|---|"]
    wrong = []
    for site in SITES:
        e = data[site]
        chain = e["chain"]
        truth, why = TRUTH[site]
        verdict = rule(site, chain)
        ok = (verdict == "third party") == (truth == "third party")
        if not ok:
            wrong.append((site, truth, why, verdict, chain))
        L.append(f"| {site} | {len(chain) - 1} | `{registrable(chain[-1])}` | "
                 f"{truth} — {why} | {verdict} | {'✓' if ok else '✗'} |")

    L += ["", "### Where the rule is wrong", ""]
    for site, truth, why, verdict, chain in wrong:
        L.append(f"- **{site}** → `{' → '.join(chain)}`. The rule says *{verdict}*, "
                 f"but it is *{truth}*: {why}. Comparing domain names cannot tell that "
                 f"two different domains belong to one organisation.")
    L += ["- **Blind spot even when it is right**: `www.korea.ac.kr` and `www.github.com` "
          "have no third-party CNAME, and the rule can only say *first party*. A site behind "
          "an anycast CDN with **no CNAME at all** (the address itself belongs to the CDN) "
          "would also be called first party — the rule looks at names, never at who owns "
          "the address. `www.stanford.edu` shows the address side: its addresses "
          "(3.33.x / 15.197.x) are AWS Global Accelerator anycast, a third party the "
          "name `netlifyglobalcdn.com` does not mention."]

    # ------------------------------------------------------------- steering
    cdn = [s for s in SITES if TRUTH[s][0] != "no CDN" and TRUTH[s][0] != "own"]
    L += ["", "## B5 · Does DNS steer you?", "",
          "Each resolver was asked twice per site, and the address sets were unioned, so "
          "plain round-robin inside one answer pool does not count as a difference. "
          "*Differs (/24)* is the stricter test: the answers do not even share a /24.", "",
          "| site | " + " | ".join(f"{n}: {r}" for n in networks for r in RESOLVERS)
          + " | differs (set) | differs (/24) |",
          "|---|" + "---|" * (len(networks) * len(RESOLVERS) + 2)]
    n_set = n_pfx = 0
    for site in SITES:
        sets = [(n, r, tuple(data[site]["answers"].get(n, {}).get(r, [])))
                for n in networks for r in RESOLVERS]
        nonempty = [s for _, _, s in sets if s]
        d_set = len(set(nonempty)) > 1
        pfx = [prefixes(s) for s in nonempty]
        d_pfx = any(not (a & b) for i, a in enumerate(pfx) for b in pfx[i + 1:])
        if site in cdn:
            n_set += d_set
            n_pfx += d_pfx
        cells = [", ".join(s) or "-" for _, _, s in sets]
        L.append(f"| {site}{'' if site in cdn else ' *(not CDN)*'} | " + " | ".join(cells)
                 + f" | {'yes' if d_set else 'no'} | {'yes' if d_pfx else 'no'} |")
    L += ["",
          f"**Steering number: {n_set} of {len(cdn)} CDN-hosted sites answered differently "
          f"to a different resolver or network** ({n_pfx} of {len(cdn)} with no /24 in common). "
          f"Networks: {', '.join(networks)}.",
          ""]
    if len(networks) >= 2:
        # Same resolver label ("system" = that network's own ISP resolver),
        # different network: does where *I* am change the answer?
        a, b = networks[0], networks[1]
        rows, x_set, x_pfx = [], 0, 0
        for site in cdn:
            ans = data[site]["answers"]
            s1, s2 = ans[a].get("system", []), ans[b].get("system", [])
            d_set = set(s1) != set(s2)
            d_pfx = not (prefixes(s1) & prefixes(s2))
            x_set += d_set
            x_pfx += d_pfx
            rows.append(f"| {site} | {', '.join(s1)} | {', '.join(s2)} | "
                        f"{'yes' if d_set else 'no'} | {'yes' if d_pfx else 'no'} |")
        L += [f"### Same question from two networks (each network's own resolver)", "",
              f"| site | {a} | {b} | differs (set) | differs (/24) |", "|---|---|---|---|---|"]
        L += rows
        L += ["", f"**Across networks: {x_set} of {len(cdn)} CDN-hosted sites answered "
              f"differently from {a} vs. {b}** ({x_pfx} with no /24 in common).", ""]
    if len(networks) < 2:
        L += ["> **One network only (path B for B3).** The two places I could measure from "
              "(cafe Wi-Fi `30coffee_5G` and `KT_PASCUCCI_5G`) both used the same KT resolver "
              "168.126.63.1, so a second run would not have been a different vantage point. "
              "Instead the comparison is between resolvers at very different distances: KT "
              "(an ISP resolver in Korea) vs. Google 8.8.8.8 and Quad9 9.9.9.9 (anycast). "
              "This weakens the conclusion: it shows that answers depend on *where the "
              "resolver is*, not that they follow *where I am*.", ""]

    part_a = os.path.join(OUT, "partA.md")
    if os.path.exists(part_a):
        L += [open(part_a, encoding="utf-8").read().strip(), ""]

    with open(os.path.join(OUT, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--collect", action="store_true")
    p.add_argument("--report", action="store_true")
    p.add_argument("--network", default="home",
                   help="label for the network you are on now (e.g. home, hotspot)")
    a = p.parse_args()
    os.makedirs(OUT, exist_ok=True)
    if a.collect:
        collect(a.network)
    elif a.report:
        report()
    else:
        p.print_help()
