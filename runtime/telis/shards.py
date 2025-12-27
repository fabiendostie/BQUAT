from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

_DEFAULT_TIER_BUDGETS = {
    "tier_1_nano": 50,
    "tier_2_micro": 500,
    "tier_3_full": 2000,
}


@dataclass(frozen=True)
class Shard:
    shard_id: str
    language: str
    version: str
    tier: str
    topics: List[str]
    tokens: int
    content: str
    source: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.shard_id,
            "language": self.language,
            "version": self.version,
            "tier": self.tier,
            "topics": list(self.topics),
            "tokens": self.tokens,
            "content": self.content,
            "source": self.source,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "Shard":
        raw_topics = data.get("topics", [])
        if isinstance(raw_topics, list):
            topics = [str(item) for item in raw_topics]
        else:
            topics = []
        raw_tokens = data.get("tokens", 0)
        if isinstance(raw_tokens, (int, float, str)):
            tokens = int(raw_tokens)
        else:
            tokens = 0
        return cls(
            shard_id=str(data.get("id", "")),
            language=str(data.get("language", "")),
            version=str(data.get("version", "")),
            tier=str(data.get("tier", "")),
            topics=topics,
            tokens=tokens,
            content=str(data.get("content", "")),
            source=str(data.get("source", "")),
            updated_at=str(data.get("updated_at", "")),
        )


@dataclass(frozen=True)
class TierBudgetPolicy:
    budgets: Dict[str, int]

    def budget_for(self, tier: str) -> int:
        return int(self.budgets.get(tier, 0))


@dataclass(frozen=True)
class ShardSearchResult:
    query: str
    language: str
    tier: str
    budget_tokens: int
    tokens_selected: int
    shards: List[Shard]


def default_tier_budgets() -> TierBudgetPolicy:
    return TierBudgetPolicy(budgets=dict(_DEFAULT_TIER_BUDGETS))


class ShardRegistry:
    def __init__(self) -> None:
        self._shards: List[Shard] = []

    def add(self, shard: Shard) -> None:
        self._shards.append(shard)

    def extend(self, shards: Iterable[Shard]) -> None:
        self._shards.extend(shards)

    def list(self, language: Optional[str] = None, tier: Optional[str] = None) -> List[Shard]:
        return [
            shard
            for shard in self._shards
            if (language is None or shard.language == language)
            and (tier is None or shard.tier == tier)
        ]

    def search(
        self,
        query: str,
        language: str,
        tier: Optional[str] = None,
        limit: Optional[int] = None,
        min_score: int = 1,
    ) -> List[Tuple[Shard, int]]:
        candidates = self.list(language=language, tier=tier)
        terms = _normalize_terms(query)
        scored: List[Tuple[Shard, int]] = []
        for shard in candidates:
            score = _score_shard(terms, shard)
            if score >= min_score:
                scored.append((shard, score))
        scored.sort(key=lambda item: (-item[1], item[0].tokens, item[0].shard_id))
        if limit is not None:
            return scored[: max(0, int(limit))]
        return scored

    def select_for_budget(
        self,
        query: str,
        language: str,
        tier: str,
        budget_tokens: int,
        limit: Optional[int] = None,
        min_score: int = 1,
    ) -> ShardSearchResult:
        scored = self.search(query, language, tier=tier, limit=limit, min_score=min_score)
        selected: List[Shard] = []
        tokens_used = 0
        for shard, _score in scored:
            if tokens_used + shard.tokens > budget_tokens:
                continue
            selected.append(shard)
            tokens_used += shard.tokens
        return ShardSearchResult(
            query=query,
            language=language,
            tier=tier,
            budget_tokens=budget_tokens,
            tokens_selected=tokens_used,
            shards=selected,
        )

    def select_for_policy(
        self,
        query: str,
        language: str,
        tier: str,
        policy: TierBudgetPolicy,
        limit: Optional[int] = None,
        min_score: int = 1,
    ) -> ShardSearchResult:
        budget = policy.budget_for(tier)
        return self.select_for_budget(
            query=query,
            language=language,
            tier=tier,
            budget_tokens=budget,
            limit=limit,
            min_score=min_score,
        )

    @classmethod
    def from_records(cls, records: Sequence[Dict[str, object]]) -> "ShardRegistry":
        registry = cls()
        registry.extend(Shard.from_dict(item) for item in records)
        return registry


def _normalize_terms(query: str) -> List[str]:
    return [term for term in query.lower().replace("-", " ").split() if term]


def _score_shard(terms: Sequence[str], shard: Shard) -> int:
    score = 0
    topics = {topic.lower() for topic in shard.topics}
    content = shard.content.lower()
    shard_id = shard.shard_id.lower()
    for term in terms:
        if term in topics:
            score += 3
        if term in shard_id:
            score += 2
        if term and term in content:
            score += 1
    return score
