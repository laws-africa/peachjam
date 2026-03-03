from typing import Any, Dict, List

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector

from peachjam.models import Offence


def search_offences(query: str, k: int = 20) -> List[Dict[str, Any]]:
    q = (query or "").strip()
    if not q:
        return []

    vector = SearchVector("title", weight="A", config="english") + SearchVector(
        "description", weight="B", config="english"
    )
    ts_query = SearchQuery(q, search_type="plain", config="english")
    rank = SearchRank(vector, ts_query)

    qs = (
        Offence.objects.annotate(rank=rank)
        # .filter(rank__gt=0.01)
        .order_by("-rank")[:k]
    )

    results: List[Dict[str, Any]] = []
    for o in qs:
        desc = (o.description or "").strip()
        results.append(
            {
                "id": o.id,
                "title": o.title,
                "provision_eid": o.provision_eid,
                "description_snippet": (desc[:220] + "…") if len(desc) > 220 else desc,
                "rank": float(o.rank or 0.0),
            }
        )
    return results
