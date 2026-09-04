"""What an event costs, when the page actually says so.

Every imported event was stored with `price_adult = 0.0`. In a numeric price
field that is not "unknown", it is "free" — and all 528 events in the live
database were making that claim. The consequence reached the user: the
personalisation scorer admits an event when `price_adult <= budget` and awards
a bonus when the budget is "free" and the price is 0, so a parent asking for
free activities was told every single event qualified. Some cost 30 €.

Measured against the live data, 44 of 528 events state a price or say entry is
free. So this cannot fill the field in — the honest outcome for the other 484
is None, which the rest of the system now has to treat as "we do not know"
rather than "nothing".

Two things are deliberately not attempted:

  A number without a currency. "2026" and "50 Joer" are not prices, and a
  parser that guesses turns an anniversary into an entrance fee.

  The word "gratis" on its own. One real listing reads "08h30 – 11h00: Gratis
  Fairtrade-Frühstück" inside the programme of an event that is not free — the
  breakfast is free, the event is not. Free is only recorded when the phrase
  is about admission: "Entrée gratuite", "Eintritt frei", "fräien Entrée".
"""
from __future__ import annotations

import re
from typing import NamedTuple, Optional


class PriceHint(NamedTuple):
    adult: Optional[float]      # None when the page does not say
    is_free: bool
    source: str                 # "event" when read from the page, else "unknown"


# Admission is free. Each alternative pairs the word with what is free, so a
# free coffee inside a paid festival does not make the festival free.
_FREE = re.compile(
    r"(?:"
    r"entr[ée]e?\s+(?:est\s+)?(?:libre|gratuite?|entièrement gratuite)"
    r"|fr[äa]ien?\s+entr[ée]e?"
    r"|eintritt\s+(?:ist\s+)?(?:frei|kostenlos|gratis)"
    r"|freier\s+eintritt"
    r"|admission\s+(?:is\s+)?free"
    r"|free\s+(?:entry|admission)"
    r"|entr[ée]e?\s*:\s*(?:gratuit|frei|free|0\s*€)"
    r"|participatioun\s+gratis"
    r")",
    re.I,
)

# A number that is explicitly money. The currency is required — without it
# "2026" and "50 Joer" become prices.
_AMOUNT = re.compile(
    r"(?<!\d)(\d{1,3})(?:[.,](\d{1,2}))?\s*(?:€|EUR\b|Euro\b)"
    r"|(?:€|EUR\b)\s*(\d{1,3})(?:[.,](\d{1,2}))?(?!\d)",
    re.I,
)

# Prices that are not an entrance fee for a visitor.
_NOT_A_FEE = re.compile(
    r"(?:preisgeld|prizemoney|prix\s+de\s+\d|gewinn|dotéiert|dotiert"
    r"|spende|don\s+libre|freiwëlleg|budget|umsatz|chiffre d'affaires)",
    re.I,
)


def read_price(*parts: Optional[str]) -> PriceHint:
    """The admission price stated in this text, or an honest "unknown".

    Free wins over an amount: a listing that says entry is free and also names
    a 30 € workshop is a free event with a paid extra, and the visitor's
    question is whether they can walk in.
    """
    text = " ".join(p for p in parts if p)
    if not text.strip():
        return PriceHint(None, False, "unknown")

    if _FREE.search(text):
        return PriceHint(0.0, True, "event")

    for match in _AMOUNT.finditer(text):
        # Skip amounts that are prize money, donations or budgets rather than
        # something a visitor pays to get in.
        window = text[max(0, match.start() - 60): match.end() + 30]
        if _NOT_A_FEE.search(window):
            continue
        whole = match.group(1) or match.group(3)
        cents = match.group(2) or match.group(4) or "0"
        try:
            value = float(f"{whole}.{cents.ljust(2, '0')[:2]}")
        except ValueError:
            continue
        # A four-figure entrance fee is a misread, not a concert ticket.
        if 0 < value <= 500:
            return PriceHint(value, False, "event")

    return PriceHint(None, False, "unknown")
