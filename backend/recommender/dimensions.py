"""The taste dimensions a clarifying question can be asked along.

Fixed rather than configurable: they are what the gap-analysis prompt offers a
model to choose from, and the question generator reads back. `catalogue` is the
instance the pipeline reads through.

How many of them one round asks about is the user's, and lives on
`RecommendConfig`; which ones exist is not.
"""

from typing import Final

from pydantic import BaseModel, ConfigDict

from backend.config.store import config_store
from backend.recommender.models import TasteDimension

# Order matters: a short answer is topped up from the front.
DIMENSIONS: Final = (
    TasteDimension(id="energy", label="Energy Level", description="Calm vs intense, quiet vs loud"),
    TasteDimension(
        id="emotional_direction",
        label="Emotional Direction",
        description="Sad, joyful, bittersweet, cathartic, neutral",
    ),
    TasteDimension(
        id="attention_level",
        label="Attention Level",
        description="Background listening vs active listening",
    ),
    TasteDimension(
        id="era", label="Era / Time Period", description="Classic, contemporary, timeless"
    ),
    TasteDimension(
        id="familiarity",
        label="Familiarity",
        description="Well-known vs deep cuts, mainstream vs obscure",
    ),
    TasteDimension(
        id="vocal_presence",
        label="Vocal Presence",
        description="Instrumental, minimal vocals, vocal-forward",
    ),
    TasteDimension(
        id="lyrical_mood",
        label="Lyrical Mood",
        description="Introspective, storytelling, abstract, anthemic",
    ),
    TasteDimension(
        id="social_context",
        label="Social Context",
        description="Solo listening, with friends, romantic, communal",
    ),
    TasteDimension(
        id="complexity",
        label="Musical Complexity",
        description="Simple and direct vs layered and complex",
    ),
    TasteDimension(
        id="rawness", label="Production Style", description="Lo-fi/raw vs polished/produced"
    ),
    TasteDimension(id="tempo", label="Tempo", description="Slow, mid-tempo, fast-paced"),
    TasteDimension(
        id="cultural_specificity",
        label="Cultural Specificity",
        description="Universal appeal vs culturally rooted",
    ),
)


class DimensionCatalogue(BaseModel):
    """The dimensions on offer, and what a model's answer about them means."""

    model_config = ConfigDict(frozen=True)

    dimensions: tuple[TasteDimension, ...] = DIMENSIONS

    def by_id(self, dimension_id: str) -> TasteDimension | None:
        """One dimension by id, or None when the model invented it."""
        return next((one for one in self.dimensions if one.id == dimension_id), None)

    def listing(self) -> str:
        """Every dimension, as the gap-analysis prompt lists them."""
        return "\n".join(dimension.line() for dimension in self.dimensions)

    def fill(self, chosen: list[str]) -> list[str]:
        """Keep the ids that exist and top up from the catalogue.

        A model that answers with one usable dimension still has to produce the
        configured number of questions, so the shortfall is filled rather than
        the round abandoned. It can also name the same dimension twice, which
        would ask it twice.

        Args:
            chosen: Dimension ids the model named, valid or not
        """
        count = config_store.get().recommend.question_count
        kept: list[str] = []
        for dimension_id in chosen:
            if self.by_id(dimension_id) is not None and dimension_id not in kept:
                kept.append(dimension_id)
        for dimension in self.dimensions:
            if len(kept) >= count:
                break
            if dimension.id not in kept:
                kept.append(dimension.id)
        return kept[:count]


catalogue = DimensionCatalogue()
