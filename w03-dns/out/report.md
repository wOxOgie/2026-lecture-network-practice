# Week 3 · Task 2 report

Networks measured: cafe-wifi  
Resolvers: system (system resolver of that network), google (8.8.8.8), quad9 (9.9.9.9)

## B4 · Who serves each site

**Rule** — a site is served by a *third party* if its CNAME chain ends in a different registrable domain than the site's own (`www.bbc.co.uk` → `bbc.co.uk`, public-suffix aware for `co.uk`/`ac.kr`). Ground truth was checked by hand.

| site | chain length | final zone | third party? (truth) | rule's verdict | match |
|---|---|---|---|---|---|
| www.microsoft.com | 2 | `akamaiedge.net` | third party — Akamai (akamaiedge.net) | third party | ✓ |
| www.netflix.com | 1 | `netflix.com` | own CDN — Netflix Open Connect, own zone | first party | ✓ |
| www.adobe.com | 2 | `akamai.net` | third party — Akamai (akamai.net) | third party | ✓ |
| www.cnn.com | 1 | `fastly.net` | third party — Fastly | third party | ✓ |
| www.apple.com | 3 | `akamaiedge.net` | third party — Akamai (edgekey -> akamaiedge) | third party | ✓ |
| www.korea.ac.kr | 0 | `korea.ac.kr` | no CDN — university server, one address | first party | ✓ |
| www.stanford.edu | 1 | `netlifyglobalcdn.com` | third party — Netlify, fronted by AWS Global Accelerator anycast | third party | ✓ |
| www.bbc.co.uk | 2 | `fastly.net` | third party — Fastly | third party | ✓ |
| www.spotify.com | 1 | `fastly.net` | third party — Fastly | third party | ✓ |
| www.github.com | 1 | `github.com` | own — GitHub's own servers (Microsoft/Azure address space) | first party | ✓ |
| www.wikipedia.org | 1 | `wikimedia.org` | own CDN — Wikimedia Foundation runs its own caching sites; wikimedia.org is the same owner | third party | ✗ |
| www.nytimes.com | 3 | `fastly.net` | third party — Fastly (via nyt.net) | third party | ✓ |

### Where the rule is wrong

- **www.wikipedia.org** → `www.wikipedia.org → dyna.wikimedia.org`. The rule says *third party*, but it is *own CDN*: Wikimedia Foundation runs its own caching sites; wikimedia.org is the same owner. Comparing domain names cannot tell that two different domains belong to one organisation.
- **Blind spot even when it is right**: `www.korea.ac.kr` and `www.github.com` have no third-party CNAME, and the rule can only say *first party*. A site behind an anycast CDN with **no CNAME at all** (the address itself belongs to the CDN) would also be called first party — the rule looks at names, never at who owns the address. `www.stanford.edu` shows the address side: its addresses (3.33.x / 15.197.x) are AWS Global Accelerator anycast, a third party the name `netlifyglobalcdn.com` does not mention.

## B5 · Does DNS steer you?

Each resolver was asked twice per site, and the address sets were unioned, so plain round-robin inside one answer pool does not count as a difference. *Differs (/24)* is the stricter test: the answers do not even share a /24.

| site | cafe-wifi: system | cafe-wifi: google | cafe-wifi: quad9 | differs (set) | differs (/24) |
|---|---|---|---|---|---|
| www.microsoft.com | 104.94.218.45 | 23.60.186.45 | 23.199.22.71 | yes | yes |
| www.netflix.com | 207.45.72.1, 207.45.73.1 | 207.45.72.1, 207.45.73.1 | 207.45.72.1, 207.45.73.1 | no | no |
| www.adobe.com | 23.32.4.146, 23.32.4.162, 23.32.4.168, 23.32.4.178, 23.32.4.187, 23.32.4.201, 23.32.4.209, 23.32.4.210, 23.32.4.227 | 23.32.56.16, 23.32.56.42 | 2.22.234.137, 2.22.234.150, 2.22.234.155 | yes | yes |
| www.cnn.com | 146.75.51.5 | 151.101.131.5, 151.101.195.5, 151.101.3.5, 151.101.67.5 | 151.101.131.5, 151.101.195.5, 151.101.3.5, 151.101.67.5 | yes | yes |
| www.apple.com | 104.94.216.37 | 184.28.183.49, 184.31.228.249 | 23.63.77.47 | yes | yes |
| www.korea.ac.kr *(not CDN)* | 163.152.6.10 | 163.152.6.10 | 163.152.6.10 | no | no |
| www.stanford.edu | 15.197.167.90, 3.33.186.135 | 15.197.167.90, 3.33.186.135 | 15.197.167.90, 3.33.186.135 | no | no |
| www.bbc.co.uk | 146.75.48.81 | 151.101.0.81, 151.101.128.81, 151.101.192.81, 151.101.64.81 | 151.101.0.81, 151.101.128.81, 151.101.192.81, 151.101.64.81 | yes | yes |
| www.spotify.com | 146.75.51.42 | 151.101.131.42, 151.101.195.42, 151.101.3.42, 151.101.67.42 | 151.101.131.42, 151.101.195.42, 151.101.3.42, 151.101.67.42 | yes | yes |
| www.github.com *(not CDN)* | 20.200.245.247 | 20.200.245.247 | 20.27.177.113 | yes | yes |
| www.wikipedia.org | 103.102.166.224 | 103.102.166.224 | 103.102.166.224 | no | no |
| www.nytimes.com | 146.75.49.164 | 151.101.1.164, 151.101.129.164, 151.101.193.164, 151.101.65.164 | 151.101.1.164, 151.101.129.164, 151.101.193.164, 151.101.65.164 | yes | yes |

**Steering number: 7 of 10 CDN-hosted sites answered differently to a different resolver or network** (7 of 10 with no /24 in common). Networks: cafe-wifi.

> **One network only (path B for B3).** The two places I could measure from (cafe Wi-Fi `30coffee_5G` and `KT_PASCUCCI_5G`) both used the same KT resolver 168.126.63.1, so a second run would not have been a different vantage point. Instead the comparison is between resolvers at very different distances: KT (an ISP resolver in Korea) vs. Google 8.8.8.8 and Quad9 9.9.9.9 (anycast). This weakens the conclusion: it shows that answers depend on *where the resolver is*, not that they follow *where I am*.
