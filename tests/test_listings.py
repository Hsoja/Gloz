import pytest

from app.listings import LISTINGS, parse_filters, search


@pytest.mark.parametrize("path", ["/", "/listings", "/about", "/privacy", "/terms", "/health"])
def test_public_pages_load(client, path):
    assert client.get(path).status_code == 200


def test_every_listing_has_a_page(client):
    for listing in LISTINGS:
        response = client.get(f"/listings/{listing.id}")
        assert response.status_code == 200
        assert listing.title in response.get_data(as_text=True)


@pytest.mark.parametrize("bad", ["nope", "../etc/passwd", "PAVILION-HOUSE", "a" * 41, "x'; DROP TABLE users;--"])
def test_unknown_or_malformed_listing_is_404(client, bad):
    assert client.get(f"/listings/{bad}").status_code == 404


def test_filter_by_deal_and_city(client):
    html = client.get("/listings?deal=rent&city=Kitchener").get_data(as_text=True)
    assert "Cedar Row Townhouse" in html
    assert "Courtyard Flat" in html
    assert "The Pavilion House" not in html


def test_invalid_filters_are_ignored():
    filters = parse_filters(
        {"deal": "steal", "city": "Atlantis", "kind": "<b>", "beds": "-3", "max_price": "1e9", "sort": "drop"}
    )
    assert filters == {
        "q": "",
        "deal": "",
        "city": "",
        "kind": "",
        "beds": 0,
        "max_price": None,
        "sort": "featured",
    }
    assert len(search(filters)) == len(LISTINGS)


def test_price_and_sort():
    results = search(parse_filters({"deal": "sale", "max_price": "1000000", "sort": "price_asc"}))
    prices = [listing.price for listing in results]
    assert prices == sorted(prices)
    assert all(price <= 1_000_000 for price in prices)


def test_query_is_length_limited_and_escaped(client):
    payload = '<img src=x onerror=alert(1)>'
    html = client.get("/listings", query_string={"q": payload}).get_data(as_text=True)
    assert payload not in html
    assert "&lt;img src=x onerror=alert(1)&gt;" in html
    assert len(parse_filters({"q": "a" * 500})["q"]) == 60


def test_no_results_shows_guidance(client):
    html = client.get("/listings?city=Guelph&beds=5&max_price=1000").get_data(as_text=True)
    assert "No homes match" in html
