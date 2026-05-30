from app.core.pagination import paginated_response


def test_paginated_response() -> None:
    items = [{"id": 1}, {"id": 2}, {"id": 3}]
    result = paginated_response(items, total=10, page=1, page_size=3)
    
    assert result["items"] == items
    assert result["total"] == 10
    assert result["page"] == 1
    assert result["page_size"] == 3


def test_paginated_response_empty() -> None:
    result = paginated_response([], total=0, page=1, page_size=10)
    
    assert result["items"] == []
    assert result["total"] == 0
    assert result["page"] == 1
    assert result["page_size"] == 10
