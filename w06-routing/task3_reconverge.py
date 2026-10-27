#!/usr/bin/env python3
"""Week 6 · Task 3 — Reconverge without recomputing the world.

Textbook §5.2.1, §5.3.

A link flaps. Every router in the area has to decide what changed. `FullRecompute`
does the honest thing: throw the table away and run Dijkstra again, from scratch,
for every event. It is correct and it is what the first implementations did.

It is also why a single flapping link in a large area used to melt the CPU of
every router that could see it.

Beat it:

    python3 bench.py
    python3 bench.py --yours

Correctness first. `bench.py` compares your table against a full recompute after
**every single event**. A router that is fast and wrong black-holes traffic.
"""
import heapq

# The harness counts how many times you run a full SPF. This is the score:
# wall-clock time in Python says more about dictionary overhead than about
# routing, but "how many times did the CPU have to recompute the world" is
# exactly what melted real routers.
SPF_RUNS = 0


def dijkstra_table(graph, source):
    """Reference shortest-path-first. Returns {destination: first_hop}.

    Use THIS function whenever you need a full recompute. Rolling your own to
    dodge the counter is not an optimisation, it is cheating the meter.
    """
    global SPF_RUNS
    SPF_RUNS += 1
    best = {source: (0, None)}
    pq, done = [(0, source, None)], set()
    while pq:
        cost, node, first_hop = heapq.heappop(pq)
        if node in done:
            continue
        done.add(node)
        best[node] = (cost, first_hop)
        for nbr, w in sorted(graph[node].items()):
            if nbr in done:
                continue
            hop = nbr if node == source else first_hop
            if cost + w < best.get(nbr, (float("inf"), None))[0]:
                best[nbr] = (cost + w, hop)
                heapq.heappush(pq, (cost + w, nbr, hop))
    return {d: h for d, (_, h) in best.items() if d != source and h}


class FullRecompute:
    """On every event, forget everything and run SPF again."""

    def __init__(self, graph, source):
        self.graph = {n: dict(e) for n, e in graph.items()}
        self.source = source
        self.table = dijkstra_table(self.graph, source)

    def link_change(self, a, b, cost):
        """cost=None means the link went down."""
        if cost is None:
            self.graph[a].pop(b, None)
            self.graph[b].pop(a, None)
        else:
            self.graph[a][b] = cost
            self.graph[b][a] = cost
        self.table = dijkstra_table(self.graph, self.source)


class YourRouter:
    """Your router. Same two methods, same table, less work per event.

    What is actually true after one link changes:

      * most destinations are not affected at all
      * a link that is not on any of your shortest paths, going *up*, can only
        matter if it creates something shorter
      * a link going *down* only matters if you were using it

    Deciding which of those applies, cheaply, without getting it wrong, is the
    task. Getting it wrong is worse than being slow - the harness will catch it
    on the event where it happens.
    """

    def __init__(self, graph, source):
        self.graph = {n: dict(e) for n, e in graph.items()}
        self.source = source
        self._recompute()

    def _recompute(self):
        """One full SPF. The table comes from dijkstra_table() (the counted run);
        the cost vector is the other half of the same computation, which a real
        SPF produces anyway and the reference function just throws away."""
        self.table = dijkstra_table(self.graph, self.source)
        self.dist = _costs(self.graph, self.source)

    def link_change(self, a, b, cost):
        """cost=None means the link went down."""
        INF = float("inf")
        old = self.graph[a].get(b, INF)
        new = INF if cost is None else cost
        if cost is None:
            self.graph[a].pop(b, None)
            self.graph[b].pop(a, None)
        else:
            self.graph[a][b] = cost
            self.graph[b][a] = cost
        if new == old:
            return

        # The table is a function of the distances and of which links are
        # "tight" (d[x] + w == d[y], i.e. on some shortest path): dijkstra_table
        # settles nodes in (cost, name) order, so each node takes its hop from
        # its first tight predecessor in that order. If neither the distances
        # nor the tight links change, the table cannot change.
        da = self.dist.get(a, INF)
        db = self.dist.get(b, INF)

        if new < old:
            # up or cheaper: only matters if it is now as short as what we have
            if da + new > db and db + new > da:
                return                                     # case 3: no SPF
            x, y = (a, b) if da + new <= db else (b, a)
            changed = self._shorten(y, self.dist[x] + new)
            self._refresh_hops(changed | {n for v in changed for n in self.graph[v]} | {a, b})
            return

        # down or dearer: only matters if we were using it
        if da + old > db and db + old > da:
            return                                         # case 2: no SPF
        y = b if da + old == db else a
        if self._still_reachable_at_same_cost(y):
            # y had another equally short way in; no distance moves, at most
            # the hops of y and whatever hangs below it
            self._refresh_hops({y})
            return
        self._recompute()                                  # a path got longer

    def _shorten(self, start, cost):
        """Push a strictly shorter cost outward from `start`. Only nodes whose
        cost actually drops are visited. Returns the set of those nodes."""
        changed, pq = set(), [(cost, start)]
        while pq:
            c, v = heapq.heappop(pq)
            if c >= self.dist.get(v, float("inf")):
                continue
            self.dist[v] = c
            changed.add(v)
            for u, w in self.graph[v].items():
                if c + w < self.dist.get(u, float("inf")):
                    heapq.heappush(pq, (c + w, u))
        return changed

    def _still_reachable_at_same_cost(self, y):
        """After the tight link into y got worse: is there another tight
        predecessor? Its cost is lower than y's, so it cannot have depended on
        that link. If y keeps its cost, nothing below y moves either."""
        d = self.dist
        for p, w in self.graph[y].items():
            if p in d and d[p] + w == d[y]:
                return True
        return False

    def _hop_of(self, v):
        """Hop of v: inherited from its first tight predecessor in (cost, name)
        order, which is exactly the one dijkstra_table() settles first."""
        d = self.dist
        best = None
        for p, w in self.graph[v].items():
            if p in d and d[p] + w == d[v] and (best is None or (d[p], p) < (d[best], best)):
                best = p
        return v if best == self.source else self.table[best]

    def _refresh_hops(self, seeds):
        """Re-derive hops for `seeds`, in (cost, name) order, and follow any
        change down to the tight successors."""
        d, src = self.dist, self.source
        pq = [(d[v], v) for v in seeds if v in d and v != src]
        heapq.heapify(pq)
        done = set()
        while pq:
            c, v = heapq.heappop(pq)
            if v in done:
                continue
            done.add(v)
            hop = self._hop_of(v)
            if self.table.get(v) != hop:
                self.table[v] = hop
                for u, w in self.graph[v].items():
                    if u in d and c + w == d[u] and u not in done:
                        heapq.heappush(pq, (d[u], u))


def _costs(graph, source):
    """Cost vector {node: cost}, run alongside each counted dijkstra_table()."""
    dist, pq = {}, [(0, source)]
    while pq:
        c, n = heapq.heappop(pq)
        if n in dist:
            continue
        dist[n] = c
        for m, w in graph[n].items():
            if m not in dist:
                heapq.heappush(pq, (c + w, m))
    return dist
