"""Sample listings and the search filter.

The listings are demo content: fictional homes illustrated with free stock photos.
They live in code (not the database) because nobody can edit them yet.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

CITIES = ("Waterloo", "Kitchener", "Guelph", "Toronto")
KINDS = ("House", "Condo", "Townhouse", "Loft", "Studio")
DEALS = ("sale", "rent")
SORTS = {
    "featured": "Featured",
    "price_asc": "Price: low to high",
    "price_desc": "Price: high to low",
    "size_desc": "Largest first",
}
MAX_QUERY = 60
MAX_PRICE = 20_000_000
SLUG_RE = re.compile(r"^[a-z0-9-]{1,40}$")


@dataclass(frozen=True)
class Listing:
    id: str
    title: str
    kind: str
    deal: str
    price: int
    city: str
    area: str
    beds: int
    baths: float
    sqft: int
    image: str
    alt: str
    summary: str
    features: tuple[str, ...] = field(default_factory=tuple)
    featured: bool = False

    @property
    def price_label(self) -> str:
        amount = f"${self.price:,}"
        return f"{amount}/mo" if self.deal == "rent" else amount

    @property
    def baths_label(self) -> str:
        return f"{self.baths:g}"


LISTINGS: tuple[Listing, ...] = (
    Listing(
        id="pavilion-house",
        title="The Pavilion House",
        kind="House",
        deal="sale",
        price=1_849_000,
        city="Waterloo",
        area="Lakeshore North",
        beds=4,
        baths=3.5,
        sqft=3200,
        image="pavilion-house",
        alt="Modern two-storey house with floor-to-ceiling windows and a lit pool at dusk",
        summary="A glass-walled family home built around a reflecting pool, with an open main floor that steps straight out to the terrace.",
        features=("Heated pool", "Double garage", "Home office", "Heat pump"),
        featured=True,
    ),
    Listing(
        id="valley-view-suite",
        title="Valley View Suite",
        kind="Condo",
        deal="sale",
        price=729_000,
        city="Guelph",
        area="River Run",
        beds=2,
        baths=2,
        sqft=1150,
        image="valley-view-suite",
        alt="Bright bathroom with a freestanding tub in front of a wall of windows overlooking hills",
        summary="Top-floor corner suite with a spa bathroom, wide windows on two sides and an unobstructed view over the valley.",
        features=("Corner unit", "Underground parking", "Gym", "Storage locker"),
        featured=True,
    ),
    Listing(
        id="cedar-townhouse",
        title="Cedar Row Townhouse",
        kind="Townhouse",
        deal="rent",
        price=3_150,
        city="Kitchener",
        area="Midtown",
        beds=3,
        baths=2.5,
        sqft=1680,
        image="cedar-townhouse",
        alt="Calm bedroom with warm wood panelling and recessed lights above the bed",
        summary="End-unit townhouse with cedar-panelled bedrooms, a private patio and a short walk to the LRT.",
        features=("End unit", "Private patio", "In-suite laundry", "Pets considered"),
        featured=True,
    ),
    Listing(
        id="heritage-manor",
        title="Ashgrove Heritage Manor",
        kind="House",
        deal="sale",
        price=2_390_000,
        city="Guelph",
        area="Old Mill",
        beds=5,
        baths=4,
        sqft=4800,
        image="heritage-manor",
        alt="Ornate sitting room with carved wooden arches and tall gothic windows",
        summary="A restored 1890s residence with hand-carved woodwork, leaded-glass windows and a modern kitchen hidden behind original panelling.",
        features=("Designated heritage", "Library", "Wine cellar", "Half-acre lot"),
    ),
    Listing(
        id="coral-terrace",
        title="Coral Terrace Residences",
        kind="Condo",
        deal="rent",
        price=2_480,
        city="Toronto",
        area="Harbourfront",
        beds=1,
        baths=1,
        sqft=640,
        image="coral-terrace",
        alt="Colourful building facade with coral and mint balconies against a blue sky",
        summary="One-bedroom suite in a landmark coral-and-mint building, steps from the waterfront trail and streetcar.",
        features=("Balcony", "Concierge", "Rooftop terrace", "Bike storage"),
    ),
    Listing(
        id="gallery-loft",
        title="The Gallery Loft",
        kind="Loft",
        deal="sale",
        price=1_095_000,
        city="Toronto",
        area="King West",
        beds=2,
        baths=2,
        sqft=1420,
        image="gallery-loft",
        alt="Long arched hallway with carved columns and a coffered skylight ceiling",
        summary="A loft inside a converted gallery building: arched corridors, a skylit atrium and ceilings over four metres high.",
        features=("Skylit atrium", "Exposed beams", "Concierge", "Parking"),
    ),
    Listing(
        id="garden-studio",
        title="Fernhill Garden Studio",
        kind="Studio",
        deal="rent",
        price=1_690,
        city="Waterloo",
        area="Uptown",
        beds=0,
        baths=1,
        sqft=480,
        image="garden-studio",
        alt="Compact lounge with two white chairs, a round table, a palm and pendant lights",
        summary="Furnished studio with a reading nook and a shared garden, close to the universities and Uptown cafés.",
        features=("Furnished", "Utilities included", "Shared garden", "Bike storage"),
    ),
    Listing(
        id="skyline-tower",
        title="Skyline Tower, Suite 2104",
        kind="Condo",
        deal="sale",
        price=865_000,
        city="Toronto",
        area="Financial District",
        beds=2,
        baths=2,
        sqft=980,
        image="skyline-tower",
        alt="White high-rise towers connected by a glass skybridge",
        summary="Twenty-first floor suite in twin towers joined by a glass skybridge, with direct access to the underground PATH.",
        features=("21st floor", "Skybridge lounge", "Pool", "24-hour security"),
    ),
    Listing(
        id="courtyard-flat",
        title="Courtyard Flat",
        kind="Condo",
        deal="rent",
        price=2_150,
        city="Kitchener",
        area="Warehouse District",
        beds=1,
        baths=1,
        sqft=720,
        image="courtyard-flat",
        alt="Black-and-white view looking up at old stone buildings around a courtyard",
        summary="Quiet flat facing an inner courtyard in a converted stone warehouse, near the tech hub and the market.",
        features=("Courtyard view", "High ceilings", "In-suite laundry", "Locker"),
    ),
)

_BY_ID = {listing.id: listing for listing in LISTINGS}


def get_listing(listing_id: str) -> Listing | None:
    if not SLUG_RE.fullmatch(listing_id or ""):
        return None
    return _BY_ID.get(listing_id)


def featured() -> list[Listing]:
    return [listing for listing in LISTINGS if listing.featured]


def _as_int(value: str | None, low: int, high: int) -> int | None:
    if value is None or not value.isdigit() or len(value) > 9:
        return None
    number = int(value)
    return number if low <= number <= high else None


def parse_filters(args) -> dict:
    """Turn query-string values into safe filters. Anything unexpected is ignored."""
    query = (args.get("q") or "").strip()[:MAX_QUERY]
    deal = args.get("deal") if args.get("deal") in DEALS else ""
    city = args.get("city") if args.get("city") in CITIES else ""
    kind = args.get("kind") if args.get("kind") in KINDS else ""
    sort = args.get("sort") if args.get("sort") in SORTS else "featured"
    beds = _as_int(args.get("beds"), 0, 5) or 0
    max_price = _as_int(args.get("max_price"), 1, MAX_PRICE)
    return {
        "q": query,
        "deal": deal,
        "city": city,
        "kind": kind,
        "beds": beds,
        "max_price": max_price,
        "sort": sort,
    }


def search(filters: dict) -> list[Listing]:
    needle = filters["q"].casefold()
    results = [
        listing
        for listing in LISTINGS
        if (not needle or needle in f"{listing.title} {listing.area} {listing.city}".casefold())
        and (not filters["deal"] or listing.deal == filters["deal"])
        and (not filters["city"] or listing.city == filters["city"])
        and (not filters["kind"] or listing.kind == filters["kind"])
        and listing.beds >= filters["beds"]
        and (filters["max_price"] is None or listing.price <= filters["max_price"])
    ]
    sort = filters["sort"]
    if sort == "price_asc":
        results.sort(key=lambda listing: listing.price)
    elif sort == "price_desc":
        results.sort(key=lambda listing: listing.price, reverse=True)
    elif sort == "size_desc":
        results.sort(key=lambda listing: listing.sqft, reverse=True)
    else:
        results.sort(key=lambda listing: not listing.featured)
    return results
