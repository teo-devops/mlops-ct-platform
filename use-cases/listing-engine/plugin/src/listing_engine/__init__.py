"""Listing Engine — the example use case of mlops-ct-platform.

Given a listing (title + price), predict its category and whether it looks
fraudulent (counterfeit, suspicious price). Two independent models, one
plugin. Inspired by a marketplace case study; nothing here is specific to any
company.
"""

from listing_engine.usecase import ListingEngine, use_case

__all__ = ["ListingEngine", "use_case"]
