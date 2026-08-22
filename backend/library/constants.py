"""Fixed literals for the library package.

Structural facts only: a date format and the width of a decade. Everything a
deployment or a listener might want to change lives on `LibraryConfig`.
"""

from typing import Final

# ISO-like dates in a title, the shape Plex uses for dated performances.
DATE_PATTERN: Final = r"\d{4}[-/]\d{2}[-/]\d{2}"

# A decade label covers its start year plus this many years.
DECADE_SPAN: Final = 9
