from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from interface.http.deps.admin_deps import AdminDeps, get_admin_deps

router = APIRouter(tags=["admin-search"])


class SearchRequest(BaseModel):
    query: str = Field(..., max_length=2000)
    top_k: int = Field(default=5, ge=1, le=50)
    threshold: float = Field(default=0.55, ge=0.0, le=1.0)


class SearchResponse(BaseModel):
    results: list[dict]
    query: str
    result_count: int


@router.post("/search/test", response_model=SearchResponse)
async def test_search(
    body: SearchRequest,
    deps: AdminDeps = Depends(get_admin_deps),
) -> SearchResponse:
    results = await deps.buscar(
        account_id=deps.account_id,
        query=body.query,
        top_k=body.top_k,
        threshold=body.threshold,
    )
    return SearchResponse(
        results=results,
        query=body.query,
        result_count=len(results),
    )
