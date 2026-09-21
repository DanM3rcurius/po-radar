"""Per-narrative deterministic signals over a cluster of items."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urlsplit

from ..models import ClusterSignals, Item, LexicalSignals
from .dedup import uniformity
from .temporal import burst_ratio

__all__ = ["cluster_signals", "registrable_domain"]

# Two-label public suffixes we care about; enough to keep co.uk-style domains
# from collapsing to "co.uk". Not a full PSL: no network, no vendored list.
_MULTI_LABEL_SUFFIXES = frozenset(
    """co.uk org.uk gov.uk ac.uk net.uk me.uk ltd.uk plc.uk sch.uk
    com.au net.au org.au edu.au gov.au co.nz net.nz org.nz govt.nz
    co.jp ne.jp or.jp ac.jp go.jp com.br net.br org.br gov.br
    co.za org.za com.mx com.ar com.tr com.cn com.hk com.sg com.my
    co.in net.in org.in gov.in co.kr or.kr com.pl com.ua co.il""".split()
)


def registrable_domain(host: str) -> str:
    """Reduce a host to its registrable domain: news.bbc.co.uk -> bbc.co.uk."""
    host = (host or "").strip().lower()
    if not host:
        return ""
    if "://" in host:
        host = urlsplit(host).netloc or host
    host = host.split("@")[-1].split("/")[0].split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    host = host.strip(".")
    labels = host.split(".")
    if len(labels) <= 2:
        return host
    if ".".join(labels[-2:]) in _MULTI_LABEL_SUFFIXES:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def _domain_of(item: Item) -> str:
    domain = registrable_domain(item.source_domain)
    if domain:
        return domain
    if item.url:
        return registrable_domain(urlsplit(item.url).netloc)
    return ""


def cluster_signals(
    items: list[Item],
    lexical: dict[str, LexicalSignals],
    now: datetime,
) -> ClusterSignals:
    """Uniformity, source diversity and burst for one narrative cluster.

    Items carrying wire attribution are excluded from uniformity and source
    diversity: twenty outlets running the same AP copy is distribution, not
    coordination. Burst is computed over every item's publication time.
    """
    if not items:
        return ClusterSignals(
            uniformity=0.0, source_diversity=1.0, burst=0.0, item_count=0, unattributed_count=0
        )

    def _attributed(item: Item) -> bool:
        signals = lexical.get(item.id)
        return bool(signals and signals.attributed_syndication)

    unattributed = [it for it in items if not _attributed(it)]
    unattributed_count = len(unattributed)

    if unattributed_count < 2:
        # Nothing to compare: a lone voice (or an all-wire cluster) is not uniform.
        uniform = 0.0
        diversity = 1.0
    else:
        uniform = uniformity([it.text for it in unattributed])
        domains = {d for d in (_domain_of(it) for it in unattributed) if d}
        diversity = min(1.0, len(domains) / unattributed_count) if domains else 1.0

    published = [it.published for it in items if it.published is not None]
    burst = burst_ratio(published, now)

    return ClusterSignals(
        uniformity=uniform,
        source_diversity=diversity,
        burst=burst,
        item_count=len(items),
        unattributed_count=unattributed_count,
    )
