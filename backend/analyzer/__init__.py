"""What a prompt implies, and what makes a seed track distinctive.

Two calls against the analysis model, split the way the rest of the backend is:

  prompts   every word sent to a model, and nothing else
  analysis  Analyzer, the clients it reads and the answers it parses

`Analyzer` is the entry point. It is built per request from the clients the
route already resolved as dependencies, so it holds no store of its own.
"""

from backend.analyzer import prompts
from backend.analyzer.analysis import Analyzer

__all__ = ["Analyzer", "prompts"]
