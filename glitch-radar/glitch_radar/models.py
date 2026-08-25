from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class Quote:
    book: str
    event: str
    market: str
    participant: str = ""
    side: str = ""
    threshold: Optional[float] = None
    odds_american: int = 0
    period: str = "game"
    timestamp: str = ""
    source: str = ""
    max_stake: Optional[float] = None

    def identity(self):
        return (
            self.event.strip().lower(),
            self.market.strip().lower(),
            self.participant.strip().lower(),
            self.side.strip().lower(),
            self.threshold,
            self.period.strip().lower(),
        )

@dataclass(frozen=True)
class Promo:
    book: str
    boost_pct: float = 0.0
    max_stake: Optional[float] = None
    min_odds_american: Optional[int] = None
    promo_type: str = "profit_boost"
