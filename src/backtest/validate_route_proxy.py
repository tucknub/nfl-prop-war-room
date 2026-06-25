from __future__ import annotations

import pandas as pd

from src.common import load_config, output_path


def validate_route_proxy(features: pd.DataFrame, real_routes: pd.DataFrame | None = None) -> pd.DataFrame:
    if real_routes is None or real_routes.empty:
        return pd.DataFrame(
            [
                {
                    "route_proxy_status": "ROUTE_PROXY_UNVALIDATED",
                    "validation_status": "NO_REAL_ROUTE_DATA_AVAILABLE",
                    "notes": "V1 marks all route estimates unvalidated until route participation is added.",
                }
            ]
        )
    merged = features.merge(real_routes, on=["season", "week", "player_id"], how="inner")
    merged["route_error"] = merged["estimated_routes"] - merged["actual_routes"]
    return pd.DataFrame(
        {
            "route_proxy_status": ["VALIDATION_DATA_AVAILABLE"],
            "validation_status": ["VALIDATED_AGAINST_REAL_ROUTES"],
            "rows": [len(merged)],
            "mae": [merged["route_error"].abs().mean()],
            "bias": [merged["route_error"].mean()],
        }
    )


def main() -> None:
    cfg = load_config()
    feature_path = output_path("receptions_feature_table.csv", cfg)
    features = pd.read_csv(feature_path, low_memory=False) if feature_path.exists() else pd.DataFrame()
    report = validate_route_proxy(features)
    report.to_csv(output_path("route_proxy_validation_report.csv", cfg), index=False)
    print("Wrote route proxy validation report")


if __name__ == "__main__":
    main()
