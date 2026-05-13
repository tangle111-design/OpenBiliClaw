"""Discovery strategies -- re-export hub for backwards compatibility."""

from openbiliclaw.discovery.strategies._utils import (
    SupportsMemoryManager,
    SupportsRankingClient,
    SupportsRelatedClient,
    SupportsSearchClient,
    SupportsSeedStrategy,
)
from openbiliclaw.discovery.strategies.douyin_direct import DouyinDirectStrategy
from openbiliclaw.discovery.strategies.explore import ExploreStrategy
from openbiliclaw.discovery.strategies.related_chain import RelatedChainStrategy
from openbiliclaw.discovery.strategies.search import SearchStrategy
from openbiliclaw.discovery.strategies.trending import TrendingStrategy

__all__ = [
    "DouyinDirectStrategy",
    "ExploreStrategy",
    "RelatedChainStrategy",
    "SearchStrategy",
    "TrendingStrategy",
    "SupportsSearchClient",
    "SupportsRankingClient",
    "SupportsRelatedClient",
    "SupportsMemoryManager",
    "SupportsSeedStrategy",
]
