"""Public pages: home, listings, listing detail and the legal pages."""

from __future__ import annotations

from flask import Blueprint, abort, g, render_template, request

from . import listings as catalogue
from .db import get_db

bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    return render_template(
        "index.html",
        featured=catalogue.featured(),
        cities=catalogue.CITIES,
        kinds=catalogue.KINDS,
        total=len(catalogue.LISTINGS),
    )


@bp.get("/listings")
def listings():
    filters = catalogue.parse_filters(request.args)
    results = catalogue.search(filters)
    return render_template(
        "listings.html",
        results=results,
        filters=filters,
        cities=catalogue.CITIES,
        kinds=catalogue.KINDS,
        sorts=catalogue.SORTS,
    )


@bp.get("/listings/<listing_id>")
def listing_detail(listing_id: str):
    listing = catalogue.get_listing(listing_id)
    if listing is None:
        abort(404)
    is_saved = False
    if g.user is not None:
        is_saved = (
            get_db()
            .execute(
                "SELECT 1 FROM saved_listings WHERE user_id = ? AND listing_id = ?",
                (g.user["id"], listing.id),
            )
            .fetchone()
            is not None
        )
    similar = [x for x in catalogue.LISTINGS if x.id != listing.id and x.city == listing.city][:3]
    return render_template("listing_detail.html", listing=listing, is_saved=is_saved, similar=similar)


@bp.get("/about")
def about():
    return render_template("about.html")


@bp.get("/privacy")
def privacy():
    return render_template("legal/privacy.html")


@bp.get("/terms")
def terms():
    return render_template("legal/terms.html")


@bp.get("/health")
def health():
    return {"status": "ok"}
