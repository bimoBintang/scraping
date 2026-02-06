"""
TikTok Social Analysis Package
Advanced social network analysis algorithms

Modules:
- Temporal Network Analysis
- Influence Cascade Tracking
- Community Evolution Analysis
- Power Law Distribution Analysis
"""

# Temporal Analysis
from .temporal import (
    TemporalNetworkAnalyzer,
    NetworkSnapshot,
    NetworkDiff,
    GrowthAnalysis,
)

# Cascade Tracking
from .cascade import (
    InfluenceCascadeTracker,
    CascadeEvent,
    CascadeNode,
    CascadeStats,
)

# Community Evolution
from .evolution import (
    CommunityEvolutionAnalyzer,
    CommunityState,
    CommunityEvent,
    CommunityEventType,
    CommunityLifecycle,
)

# Power Law Analysis
from .power_law import (
    PowerLawAnalyzer,
    PowerLawFit,
    DistributionComparison,
    HeavyTailMetrics,
)


__all__ = [
    # Temporal
    'TemporalNetworkAnalyzer',
    'NetworkSnapshot',
    'NetworkDiff',
    'GrowthAnalysis',
    
    # Cascade
    'InfluenceCascadeTracker',
    'CascadeEvent',
    'CascadeNode',
    'CascadeStats',
    
    # Evolution
    'CommunityEvolutionAnalyzer',
    'CommunityState',
    'CommunityEvent',
    'CommunityEventType',
    'CommunityLifecycle',
    
    # Power Law
    'PowerLawAnalyzer',
    'PowerLawFit',
    'DistributionComparison',
    'HeavyTailMetrics',
]

__version__ = '1.0.0'
