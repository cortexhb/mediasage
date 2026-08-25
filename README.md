# MediaSage for Plex

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker Hub](https://img.shields.io/badge/docker-cortexhb%2Fmediasage-blue)](https://hub.docker.com/r/cortexhb/mediasage)
[![GHCR](https://img.shields.io/badge/ghcr-cortexhb%2Fmediasage-blue)](https://ghcr.io/cortexhb/mediasage)
[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)

**AI-powered playlists and album recommendations for Plex—using only music you actually own.**

MediaSage is a self-hosted web app that creates playlists and recommends albums by combining LLM intelligence with your
Plex library. Every suggestion is guaranteed playable because it only considers music you have.

*Sample Generated Playlist:*
![MediaSage Screenshot](docs/images/screenshot-playlist.png)

*Sample Generated Album Recommendation:*
![MediaSage Screenshot](docs/images/screenshot-album.png)

*Home Screen:*
![MediaSage Screenshot](docs/images/screenshot-home.png)

*Playlist Flow:*
![MediaSage Screenshot](docs/images/screenshot-playlist-start.png)

*Album Flow:*
![MediaSage Screenshot](docs/images/screenshot-album-start.png)

---

## Quick Start

```bash
docker run -d \
  --name mediasage \
  -p 5765:5765 \
  -v mediasage-data:/app/data \
  --restart unless-stopped \
  ghcr.io/cortexhb/mediasage:latest
```

Open **http://localhost:5765** — a setup wizard walks you through connecting Plex, choosing an AI provider, and syncing
your library.

You can also pass credentials as environment variables to skip the wizard. See [Configuration](#configuration) for
details.

**Requirements:** Docker, a Plex server with music,
a [Plex token](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/), and an API key
from Google, Anthropic, or OpenAI (or a local model via Ollama).

---

## Contents

- [Why MediaSage?](#why-mediasage)
- [Features](#features)
- [Installation](#installation)
- [Configuration](#configuration)
- [How It Works](#how-it-works)
- [Development](#development)
- [API Reference](#api-reference)

---

## Why MediaSage?

**Plex users with personal music libraries have few good options for AI playlists.**

Plexamp's built-in Sonic Sage used ChatGPT to generate playlists, but it was designed around Tidal streaming. The AI
recommended tracks from an unlimited catalog, and Tidal made them playable. The "limit to library" setting just hid
results you didn't own—so if you asked for 25 tracks and only 4 existed in your library, you got a 4-track playlist.

When [Tidal integration ended in October 2024](https://forums.plex.tv/t/tidal-integration-with-plex-ending-october-28-2024/885728),
Sonic Sage lost its foundation. Generic tools like ChatGPT have the same problem: they recommend from an infinite
catalog with no awareness of what you actually own.

**MediaSage inverts the approach:**

| Filter-Last (Sonic Sage, ChatGPT)   | Filter-First (MediaSage)   |
|-------------------------------------|----------------------------|
| AI recommends from infinite catalog | AI only sees your library  |
| Hide missing tracks after           | No missing tracks possible |
| Near-empty playlists                | Full playlists, every time |

The result: every track in every playlist exists in your Plex library and plays immediately.

---

## Features

### Playlist Generation

Create playlists two ways:

**Describe what you want** — Natural language prompts like:

- "Melancholy 90s alternative for a rainy day"
- "Upbeat instrumental jazz for a dinner party"
- "Late night electronic, nothing too aggressive"

**Start from a song** — Pick a track you love, then explore musical dimensions: mood, era, instrumentation, genre,
production style. Select which qualities you want more of.

### Album Recommendations

Describe a mood or moment, answer two quick questions about your preferences, and get a single perfect album to listen
to—with an editorial pitch explaining why it fits.

- **Library mode** — recommends albums you own, ready for instant playback
- **Discovery mode** — suggests albums you don't own yet, based on your taste profile
- **Familiarity control** — choose between comfort picks, hidden gems, or rediscoveries
- **Show Me Another** — regenerate without starting over
- Primary recommendation with a full write-up, plus two secondary picks

### Smart Filtering

Before the AI sees anything, you control the pool:

- **Genres** — Select from your library's actual genre tags
- **Decades** — Filter by era
- **Minimum rating** — Only tracks rated 3+, 4+, etc.
- **Exclude live versions** — Skip concert recordings automatically

Real-time track counts show exactly how your filters narrow results.

### Local Library Cache

MediaSage syncs your Plex library to a local SQLite database. After a one-time sync (~2 min for 18,000 tracks), all
library operations—filtering, counting, sending to AI—happen locally in milliseconds instead of waiting on Plex.

- **Setup wizard** walks you through first-run configuration and sync
- **Footer status** shows track count and last sync time
- **Auto-refresh** keeps cache current (syncs if >24h stale)
- **Manual refresh** available anytime

### Multi-Provider Support

Bring your own API key—or run locally:

| Provider             | Max Tracks   | Typical Cost  | Best For                            |
|----------------------|--------------|---------------|-------------------------------------|
| **Google Gemini**    | ~18,000      | $0.03 – $0.25 | Large libraries, lowest cost        |
| **Anthropic Claude** | ~3,500       | $0.15 – $0.25 | Nuanced recommendations             |
| **OpenAI GPT**       | ~2,300       | $0.05 – $0.10 | Solid all-around                    |
| **Ollama** ⚗️        | Varies       | Free          | Privacy, local inference            |
| **Custom** ⚗️        | Configurable | Free          | Self-hosted, OpenAI-compatible APIs |

⚗️ *Local LLM support is experimental. [Report issues](https://github.com/cortexhb/mediasage/issues).*

> **Free option:** Google Gemini offers a free API tier that's more than enough for personal use — no credit card
> required. See the [Gemini free credit guide](docs/gemini-free-credit-guide.md) for setup instructions and details.

Estimated cost displays before you generate. MediaSage auto-detects your provider based on which key you configure.

### Play and Save

- **Play Now** — send tracks directly to any Plex device for instant playback
- **Create** a new playlist, **replace** an existing one, or **append** tracks to one
- Device picker shows all active Plex clients with status indicators
- Duplicate detection when appending to existing playlists
- Preview tracks with album art before saving
- Remove tracks you don't want
- Rename the playlist
- See actual token usage and cost

---

## Installation

### Docker Compose (Recommended)

```bash
mkdir mediasage && cd mediasage
curl -O https://raw.githubusercontent.com/cortexhb/mediasage/main/docker-compose.yml
curl -O https://raw.githubusercontent.com/cortexhb/mediasage/main/.env.example
mv .env.example .env
```

Edit `.env`:

```bash
MEDIASAGE_PLEX__URL=http://your-plex-server:32400
MEDIASAGE_PLEX__TOKEN=your-plex-token

# Pick a provider and give it a key. Both are required.
MEDIASAGE_LLM__PROVIDER=gemini
MEDIASAGE_LLM__API_KEY=your-gemini-key
MEDIASAGE_LLM__MODEL_ANALYSIS=gemini-2.5-flash
MEDIASAGE_LLM__MODEL_GENERATION=gemini-2.5-flash
```

Start:

```bash
docker compose up -d
```

### NAS Platforms

<details>
<summary><strong>Synology (Container Manager)</strong></summary>

**GUI:**

1. **Container Manager** → **Registry** → Search `ghcr.io/cortexhb/mediasage`
2. Download `latest` tag
3. **Container** → **Create**
4. Port: 5765 → 5765
5. Add environment variables: `MEDIASAGE_PLEX__URL`, `MEDIASAGE_PLEX__TOKEN`, `MEDIASAGE_LLM__API_KEY`

**Docker Compose:**

```bash
mkdir -p /volume1/docker/mediasage && cd /volume1/docker/mediasage
curl -O https://raw.githubusercontent.com/cortexhb/mediasage/main/docker-compose.yml
curl -O https://raw.githubusercontent.com/cortexhb/mediasage/main/.env.example
mv .env.example .env && nano .env
```

Then in **Container Manager** → **Project** → **Create**, point to `/volume1/docker/mediasage`.

**No Docker?** Some Synology models (especially ARM-based units) don't support Docker/Container Manager.
See [Bare Metal](#bare-metal-no-docker) below for running MediaSage directly with Python.

</details>

<details>
<summary><strong>Unraid</strong></summary>

1. **Docker** → **Add Container**
2. Repository: `ghcr.io/cortexhb/mediasage:latest`
3. Port: 5765 → 5765
4. Add variables: `MEDIASAGE_PLEX__URL`, `MEDIASAGE_PLEX__TOKEN`, `MEDIASAGE_LLM__API_KEY`

</details>

<details>
<summary><strong>TrueNAS SCALE</strong></summary>

1. **Apps** → **Discover Apps** → **Custom App**
2. Image: `ghcr.io/cortexhb/mediasage`, Tag: `latest`
3. Port: 5765
4. Add environment variables

</details>

<details>
<summary><strong>Portainer</strong></summary>

**Stacks** → **Add Stack**:

```yaml
services:
  mediasage:
    image: ghcr.io/cortexhb/mediasage:latest
    ports:
      - "5765:5765"
    environment:
      - MEDIASAGE_PLEX__URL=http://your-server:32400
      - MEDIASAGE_PLEX__TOKEN=your-token
      - MEDIASAGE_LLM__API_KEY=your-key
    volumes:
      - ./data:/app/data
    restart: unless-stopped
```

</details>

### Bare Metal (No Docker)

Docker isn't required. MediaSage is Python + FastAPI with no native dependencies, so it runs on any machine with Python
3.14+ and [uv](https://docs.astral.sh/uv/) — including ARM-based Synology NAS models, Raspberry Pis, or any
Linux/macOS/Windows box.

```bash
git clone https://github.com/cortexhb/mediasage.git
cd mediasage
uv sync
```

Set your environment variables:

```bash
export MEDIASAGE_PLEX__URL=http://your-plex-server:32400
export MEDIASAGE_PLEX__TOKEN=your-plex-token
export MEDIASAGE_LLM__API_KEY=your-gemini-key
```

Start the server:

```bash
uv run uvicorn backend.main:app --host 0.0.0.0 --port 5765
```

Access at **http://your-machine-ip:5765**.

<details>
<summary><strong>Running as a background service (systemd)</strong></summary>

To keep MediaSage running after you close your terminal, create a systemd service:

```ini
# /etc/systemd/system/mediasage.service
[Unit]
Description = MediaSage
After = network.target

[Service]
Type = simple
User = your-user
WorkingDirectory = /path/to/mediasage
EnvironmentFile = /path/to/mediasage/.env
ExecStart = /path/to/mediasage/.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 5765
Restart = on-failure

[Install]
WantedBy = multi-user.target
```

```bash
sudo systemctl enable mediasage
sudo systemctl start mediasage
```

</details>

---

## Configuration

Every section, every field, every default: the [configuration reference](docs/configuration.md).
What follows is the part most deployments need.

### Environment Variables

Every setting is reachable as `MEDIASAGE_<SECTION>__<FIELD>`. Sections nest with a double
underscore. Environment variables override `.env`, which overrides the YAML files.

| Variable                        | Required | Description                                                                                                          |
|---------------------------------|----------|----------------------------------------------------------------------------------------------------------------------|
| `MEDIASAGE_PLEX__URL`           | Yes      | Plex server URL (e.g., `http://192.168.1.100:32400`)                                                                 |
| `MEDIASAGE_PLEX__TOKEN`         | Yes      | [Plex authentication token](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/) |
| `MEDIASAGE_PLEX__MUSIC_LIBRARY` | No       | Library name if not "Music"                                                                                          |
| `MEDIASAGE_LLM__PROVIDER`       | **Yes**  | `anthropic`, `openai`, `gemini`, `ollama` or `custom`                                                                |
| `MEDIASAGE_LLM__API_KEY`        | Cloud    | API key for the selected provider                                                                                    |
| `MEDIASAGE_LLM__ENDPOINT_URL`   | Local    | Endpoint for `ollama` or `custom`                                                                                    |
| `MEDIASAGE_LLM__CONTEXT_WINDOW` | Local    | Context window in tokens, between 512 and 2,000,000                                                                  |
| `MEDIASAGE_LLM__MODEL_ANALYSIS` | No       | Analysis model name                                                                                                  |
| `MEDIASAGE_LLM__MODEL_GENERATION` | No     | Generation model name                                                                                                |
| `MEDIASAGE_DEFAULTS__TRACK_COUNT` | No     | Default playlist length shown in the UI (default: 25)                                                                |

MediaSage does not guess on your behalf. There is no default provider, and no table of default
model names — one would go stale and quietly send requests to a model you did not choose. A missing
or incomplete LLM section is rejected at startup rather than at the moment you try to use it.

### Tuning

Nothing that varies between one deployment and the next is baked into the code. Every value below
has a working default and is only worth touching when your setup differs; the shape of each
section is in `backend/config/models.py`, with a comment on every field.

| Section | Prefix | What it tunes |
|---------|--------|---------------|
| Plex | `MEDIASAGE_PLEX__` | Bulk page size, request timeout, reconnect cooldown, retry backoff |
| Library | `MEDIASAGE_LIBRARY__` | Sync batch size, staleness, what counts as a live recording |
| Budget | `MEDIASAGE_BUDGET__` | How much of the library fits in one prompt |
| Matching | `MEDIASAGE_MATCHING__` | Fuzzy floors for matching a name back to your library |
| Recommend | `MEDIASAGE_RECOMMEND__` | Session lifetime and cap, questions and picks per round |
| Research | `MEDIASAGE_RESEARCH__` | Source endpoints, rate limit, how much of each source is kept |
| Art | `MEDIASAGE_ART__` | Proxy timeout, cache lifetimes, the external host allowlist |

Two of these are worth knowing about:

- **Matching floors** are rapidfuzz scores, 0–100. Clean tags tolerate a high floor; a library full
  of `(Remastered 2011)` suffixes needs a lower one. Too low and a recommendation plays the wrong
  record; too high and good matches are dropped and silently skipped.
- **Research endpoints** take a local mirror. If you run the MusicBrainz Docker mirror, point
  `MEDIASAGE_RESEARCH__MUSICBRAINZ_URL` at it and drop `MEDIASAGE_RESEARCH__MUSICBRAINZ_INTERVAL`
  to `0` — the one-second default exists to stay inside the public server's published rate limit,
  which your own mirror does not have.

List-valued settings are JSON arrays: `MEDIASAGE_ART__EXTERNAL_DOMAINS='["coverartarchive.org"]'`.

### Web UI Configuration

You can also configure MediaSage through the **Settings** page in the web UI. Settings entered there are saved to
`config.user.yaml` and persist across restarts. Environment variables always take priority over UI-saved settings.

### Advanced: config.yaml

Mount a config file for additional options:

```yaml
plex:
  music_library: "Music"

llm:
  provider: "gemini"
  model_analysis: "gemini-2.5-flash"
  model_generation: "gemini-2.5-flash"
  smart_generation: false  # true = use smarter model for both (higher quality, ~3-5x cost)

defaults:
  track_count: 25
```

### LLM Tracing (Optional)

MediaSage can send every LLM call to [Langfuse](https://langfuse.com) so you can inspect prompts,
replies, token counts and cost. It is off unless you supply keys. See the
[Langfuse tracing guide](docs/langfuse_tracing.md).

Token counts and cost are reported by the provider after a run, never predicted before one. See
[token accounting](docs/token_accounting.md).

### Model Selection

MediaSage uses a two-model strategy by default:

| Role           | Purpose                                                 | Models Used                                        |
|----------------|---------------------------------------------------------|----------------------------------------------------|
| **Analysis**   | Interpret prompts, suggest filters, analyze seed tracks | claude-sonnet-4-5 / gpt-4.1 / gemini-2.5-flash     |
| **Generation** | Select tracks from filtered list                        | claude-haiku-4-5 / gpt-4.1-mini / gemini-2.5-flash |

This balances quality with cost. Enable `smart_generation: true` to use the analysis model for everything.

### Local LLM Setup (Experimental)

Run MediaSage with local models for privacy and zero API costs.

<details>
<summary><strong>Ollama</strong></summary>

1. Install [Ollama](https://ollama.ai) and pull a model:
   ```bash
   ollama pull llama3:8b
   ```

2. Configure MediaSage via environment or Settings UI:
   ```bash
   MEDIASAGE_LLM__PROVIDER=ollama
   MEDIASAGE_LLM__ENDPOINT_URL=http://localhost:11434
   MEDIASAGE_LLM__CONTEXT_WINDOW=32768
   ```

3. Select your model in Settings → the context window is auto-detected.

**Recommended models:** `llama3:8b`, `qwen3:8b`, `mistral` — models with 8K+ context work best.

</details>

<details>
<summary><strong>Custom OpenAI-Compatible API</strong></summary>

For LM Studio, text-generation-webui, vLLM, or any OpenAI-compatible server:

1. Start your server with an OpenAI-compatible endpoint

2. Configure in Settings:
    - **API Base URL:** `http://localhost:5000/v1`
    - **API Key:** If required by your server
    - **Model Name:** The model identifier
    - **Context Window:** Your model's context size

</details>

**Note:** Local models are slower and may produce less accurate results than cloud providers. A 10-minute timeout is
used for generation. Models with larger context windows will support more tracks.

---

## How It Works

MediaSage uses a **filter-first architecture** designed for large libraries (50,000+ tracks):

```
┌─────────────────────────────────────────────────────────────────┐
│  1. ANALYZE                                                      │
│     LLM interprets your prompt → suggests genre/decade filters   │
├─────────────────────────────────────────────────────────────────┤
│  2. FILTER                                                       │
│     Plex library narrowed to matching tracks                     │
│     "90s Alternative" → 2,000 tracks                             │
├─────────────────────────────────────────────────────────────────┤
│  3. SAMPLE                                                       │
│     If too large for context, randomly sample                    │
│     Fits within model's token limits                             │
├─────────────────────────────────────────────────────────────────┤
│  4. GENERATE                                                     │
│     Filtered track list + prompt sent to LLM                     │
│     LLM selects best matches from available tracks               │
├─────────────────────────────────────────────────────────────────┤
│  5. MATCH                                                        │
│     Fuzzy matching links LLM selections to library               │
│     Handles minor spelling/formatting differences                │
├─────────────────────────────────────────────────────────────────┤
│  6. SAVE                                                         │
│     Playlist created in Plex                                     │
│     Ready in Plexamp or any Plex client                          │
└─────────────────────────────────────────────────────────────────┘
```

This ensures every track exists in your library while keeping API costs manageable.

---

## Development

### Local Setup

```bash
git clone https://github.com/cortexhb/mediasage.git
cd mediasage
uv sync

export MEDIASAGE_PLEX__URL=http://your-plex-server:32400
export MEDIASAGE_PLEX__TOKEN=your-plex-token
export MEDIASAGE_LLM__API_KEY=your-key

uv run uvicorn backend.main:app --reload --port 5765
```

### Testing

```bash
uv run pytest
uv run ruff check .
```

### Tech Stack

- **Backend:** Python 3.14+, FastAPI, python-plexapi, rapidfuzz, httpx
- **Frontend:** Vanilla HTML/CSS/JS (no build step)
- **LLM SDKs:** anthropic, openai, google-genai (+ Ollama via REST API)
- **Deployment:** Docker

---

## API Reference

Interactive documentation available at `/docs` when running.

| Endpoint                        | Method     | Description                             |
|---------------------------------|------------|-----------------------------------------|
| `/api/health`                   | GET        | Health check                            |
| `/api/config`                   | GET/POST   | Get or update configuration             |
| `/api/setup/status`             | GET        | Onboarding checklist state              |
| `/api/setup/validate-plex`      | POST       | Validate Plex credentials               |
| `/api/setup/validate-ai`        | POST       | Validate AI provider credentials        |
| `/api/setup/complete`           | POST       | Mark setup wizard as complete           |
| `/api/library/stats`            | GET        | Library statistics                      |
| `/api/library/status`           | GET        | Cache state, track count, sync progress |
| `/api/library/sync`             | POST       | Trigger background library sync         |
| `/api/library/search`           | GET        | Search library tracks                   |
| `/api/analyze/prompt`           | POST       | Analyze natural language prompt         |
| `/api/analyze/track`            | POST       | Analyze a seed track                    |
| `/api/filter/preview`           | POST       | Preview filtered track list             |
| `/api/generate`                 | POST       | Generate playlist                       |
| `/api/generate/stream`          | POST       | Stream playlist generation (SSE)        |
| `/api/playlist`                 | POST       | Save playlist to Plex                   |
| `/api/playlist/update`          | POST       | Replace or append to a playlist         |
| `/api/recommend/albums/preview` | GET        | Preview album candidates for filters    |
| `/api/recommend/analyze-prompt` | POST       | Analyze prompt for genre/decade filters |
| `/api/recommend/questions`      | POST       | Generate clarifying questions           |
| `/api/recommend/generate`       | POST       | Generate album recommendations          |
| `/api/recommend/switch-mode`    | POST       | Switch library/discovery mode           |
| `/api/results`                  | GET        | List saved result history               |
| `/api/results/{id}`             | GET/DELETE | Get or delete a saved result            |
| `/api/plex/clients`             | GET        | List active Plex clients                |
| `/api/plex/playlists`           | GET        | List existing Plex playlists            |
| `/api/play-queue`               | POST       | Send tracks to a Plex client            |
| `/api/art/{rating_key}`         | GET        | Proxy album art from Plex               |
| `/api/ollama/status`            | GET        | Ollama connection status                |
| `/api/ollama/models`            | GET        | List available Ollama models            |
| `/api/ollama/model-info`        | GET        | Get model details (context window)      |

---

## License

MIT
