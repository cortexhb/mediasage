"""The HTTP surface, one package per resource.

  health.py   GET /api/health -- both dependencies, without touching either
  setup/      /api/setup -- the onboarding wizard and its validations
  plex/       /api/plex/link and /api/plex/server -- the browser sign-in
  config/     /api/config and /api/ollama -- settings, and what fills them in
  library/    /api/library -- the local mirror: status, sync, stats, search
  analyze/    /api/analyze and /api/filter/preview -- what a prompt implies
  playlists/  /api/generate, /api/playlist, /api/plex, /api/play-queue
  recommend/  /api/recommend -- album recommendations, questions first
  results/    /api/results -- the saved history
  art/        /api/art and /api/external-art -- album art, proxied
  static.py   / and /static -- the frontend

Each package's `__init__.py` opens with a map of its modules and exposes the
one `register_*_routes(app)` that `app.py` mounts, so splitting a resource
into modules never changes the mount order. `health.py` and `static.py` stay
flat: they serve one thing each and have nothing to split.

Mount order is significant where a literal path could be read as a parameter
of a shorter one, and each of those carries a comment saying so.
"""
