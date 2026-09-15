from __future__ import annotations

import research_data
from app import main


def _clear_role_data_caches() -> None:
    for name in (
        "load_operational_status",
        "load_role_data",
        "load_situational_data",
        "load_production_data",
        "load_opportunity_events",
    ):
        loader = getattr(research_data, name, None)
        cache_clear = getattr(loader, "cache_clear", None)
        if callable(cache_clear):
            cache_clear()


if __name__ == "__main__":
    _clear_role_data_caches()
    main()
