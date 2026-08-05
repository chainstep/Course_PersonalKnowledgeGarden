from __future__ import annotations


def reciprocal_rank_fusion(ranks: list[list[str]], constant: int = 60) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranking in ranks:
        for index, key in enumerate(ranking, 1):
            scores[key] = scores.get(key, 0.0) + 1.0 / (constant + index)
    return scores
