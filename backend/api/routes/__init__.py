"""The HTTP surface, one module per resource.

  health.py     GET /api/health -- both dependencies, without touching either
  setup.py      /api/setup -- the onboarding wizard and its validations
  config.py     /api/config and /api/ollama -- reading and changing settings
  library.py    /api/library -- the local mirror: status, sync, stats, search
  analyze.py    /api/analyze and /api/filter/preview -- what a prompt implies
  playlists.py  /api/generate, /api/playlist, /api/play-queue -- playlists
  recommend.py  /api/recommend -- album recommendations, questions first
  results.py    /api/results -- the saved history
  art.py        /api/art and /api/external-art -- album art, proxied
  static.py     / and /static -- the frontend

Each exposes one `register_*_routes(app)` and nothing else. Mount order is
significant where a literal path could be read as a parameter of a shorter
one, and each of those carries a comment saying so.
"""
