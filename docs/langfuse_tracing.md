# LLM Tracing With Langfuse

MediaSage can send every LLM call it makes to [Langfuse](https://langfuse.com), where you can see
what was asked, what came back, how long it took, how many tokens it burned, and what it cost.

Tracing is **off by default** and entirely optional. MediaSage works exactly the same without it.
Nothing is sent anywhere unless you supply keys.

## Why Turn It On

- **See what the model actually got.** Playlist quality problems are usually prompt problems. The
  trace shows the full prompt, including the filtered track list that was sent.
- **Understand cost.** Every generation records the provider's own token counts, so you get real
  numbers rather than estimates.
- **Debug slow or failed runs.** A run that stalls shows exactly which call was in flight.
- **Compare models.** Switch the analysis or generation model and compare the traces side by side.

If none of that interests you, skip this page.

## What Gets Traced

Each user-facing operation becomes one trace, named for what it does:

- `mediasage:playlist-generation` — generating a playlist from a prompt
- `mediasage:recommendation-round` — a round of album recommendations
- `mediasage:analyze-prompt` — working out which genres and decades a prompt implies
- `mediasage:analyze-track` — working out the dimensions of a seed track

Each trace opens with what was asked — the prompt, the genres and decades, the track count — and
closes with what came out: the playlist title, the narrative, and the tracks that were picked. Inside
it, every individual model call appears as a generation with its own prompt, reply, model name and
token counts.

**Traces are grouped into sessions.** Everything one flow spends — the clarifying questions, the
prompt analysis, the generation itself — shares a single session id, so in the Langfuse UI you can
open one session and see the whole journey from "moody jazz for a rainy evening" to the finished
playlist, rather than four unrelated traces.

## What Is Not Sent

- **No Plex token, no LLM API key.** Neither is part of a prompt or a trace attribute.
- **No user identity.** MediaSage has no accounts, so there is nobody to identify.
- **Your library metadata is part of the prompt.** This is worth being deliberate about: the
  filtered candidate list — track titles, artists, albums — is what MediaSage sends to the model,
  so it is what appears in the trace. If you would rather that not leave your network, run Langfuse
  self-hosted, or leave tracing off.

## Turning It On

You need three values from a Langfuse project (Settings → API Keys): a host, a public key, and a
secret key. A free cloud account works; so does a self-hosted instance.

### Environment Variables (Recommended)

| Variable                       | Example                      | Notes                               |
| ------------------------------ | ---------------------------- | ----------------------------------- |
| `LANGFUSE_BASE_URL`            | `https://cloud.langfuse.com` | EU cloud, US cloud, or your own URL |
| `LANGFUSE_PUBLIC_KEY`          | `pk-lf-...`                  |                                     |
| `LANGFUSE_SECRET_KEY`          | `sk-lf-...`                  | Keep out of version control         |
| `LANGFUSE_TRACING_ENVIRONMENT` | `production`                 | Optional; tags and filters traces   |

All three of base URL, public key and secret key must be present. With any one of them missing,
tracing stays off — there is no half-configured state that silently drops traces.

`LANGFUSE_TRACING_ENVIRONMENT` is optional and only decides which environment the traces are filed
under in the Langfuse UI. It is worth setting if one Langfuse project receives traces from more than
one MediaSage deployment — for example a `staging` box and a `production` one — so you can tell them
apart.

With Docker Compose, put them in a `.env.langfuse` file next to `docker-compose.yml`:

```
LANGFUSE_BASE_URL=https://cloud.langfuse.com
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_TRACING_ENVIRONMENT=production
```

The bundled `docker-compose.yml` already loads that file, and it should be in `.gitignore`.

### Config File

The same four values can live in `config.yaml` under a `langfuse:` section instead — see
`config.example.yaml`. Environment variables win over the file, so you can keep the base URL and
environment in the config and pass only the secret key from the environment.

Putting a secret key in a config file is the less careful option. Prefer the environment.

### Restart to Apply

Unlike most MediaSage settings, tracing is not hot-reloadable. The Langfuse client is built once
when the app starts, so changing keys means restarting the container. Saving new keys into a running
instance will not take effect.

## Checking That It Works

Generate a playlist, then open your Langfuse project. A trace named `mediasage:playlist-generation`
should appear within a few seconds. If it does not:

- Confirm all three values are set, and that the base URL includes the scheme (`https://`).
- Confirm you restarted after setting them.
- Check the MediaSage startup logs. When tracing is off, they say so explicitly:
  `Langfuse tracing off: no base URL or keys configured`.
- Confirm the container can reach the Langfuse host — a home-lab firewall blocking outbound HTTPS is
  a common cause.

## Performance and Failure Behaviour

Traces are batched and sent in the background, so tracing does not sit in the path of a playlist
being generated. If Langfuse is unreachable or the keys are wrong, MediaSage keeps working normally
and the traces are simply lost — a tracing failure never fails a generation.

## Turning It Off

Remove the keys (or blank them) and restart. With nothing configured, no client connects and no data
leaves the machine.
