"""
enrich.py — the AI seam. Does nothing today, on purpose.

Every field result passes through an Enricher before rendering. The default
NullEnricher returns results untouched, so the tool is 100% deterministic and
offline: no model, no network, no inference.

WHY THE HOOK EXISTS NOW
-----------------------
The AI-enhanced features (auto-suggesting which sections matter, summarising a
captured section, proposing an output layout) are explicitly a later phase and
are NOT mission critical. But retrofitting them later is only cheap if there is
already a single, well-defined place where a field result can be inspected and
annotated. That place is here.

THE CONSTRAINT ANY FUTURE ENRICHER MUST RESPECT
-----------------------------------------------
The security goal is that data never leaves the device. So an enrichment step
may only ever use a LOCAL model (e.g. a small model served on localhost). It
must never call a hosted API. An enricher that reaches the internet would
silently void the whole reason this tool exists.

DESIGN RULE FOR LATER
---------------------
Enrichment is ADDITIVE and clearly labelled. It may add a `suggestion` to a
field; it must never overwrite an extracted `value` or a `citation`. A reviewer
must always be able to tell what was mechanically extracted from the document
versus what a model proposed. Mixing the two would destroy the audit trail that
makes this tool acceptable in a regulated setting.
"""


class Enricher:
    def enrich(self, records, context=None):
        raise NotImplementedError


class NullEnricher(Enricher):
    """The only enricher that exists today: a pass-through."""

    name = "none"
    enabled = False

    def enrich(self, records, context=None):
        return records


def get_enricher(_mode="none"):
    """Always returns the pass-through today. Future modes plug in here."""
    return NullEnricher()
