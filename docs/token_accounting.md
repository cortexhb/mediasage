# Token Accounting

How MediaSage reports what a run spends, and why it does not predict it beforehand. Covers the
preview endpoints, the token counts on responses, and the one approximation that remains.

## The Rule

Token counts are either taken from the provider or not shown. Nothing in the backend predicts them.

A count that comes back on a response is what the provider charged. A count that would have to be
guessed is not displayed, not stored, and not used to quote a price.

## What the Preview Endpoints Answer

`POST /api/filter/preview` and `GET /api/recommend/albums/preview` answer row counts and nothing
else: how many tracks or albums match the selection, and how many of those the user's own cap lets
through (`backend/models.py:170-194`, `backend/recommender/models.py:206-230`). The match count is
a `COUNT(*)` against the local cache, or against Plex until one has been synced. The second number
is arithmetic on the cap the user set.

Neither endpoint takes the configuration any more, because neither has a price to apply.

## Where Real Counts Come From

`LLMResponse.from_message` reads `usage_metadata` off the LangChain reply
(`backend/llm/models.py:81`). Those are the provider's own numbers for the call that just ran.

`LLMConfig.estimate_cost` multiplies them by the prices the user declared
(`backend/config/models.py:183-192`). An unset price is `0.0`, which the UI reports as no cost
rather than as a wrong one, and local inference is always `0.0`.

- A provider that reports no usage yields zero tokens and zero cost. `usage_metadata` is absent, and
  `from_message` defaults each field to `0`. There is no fallback estimate.
- Counts appear only after the work is paid for. The filters screen shows how much of the library a
  selection reaches; the footer shows tokens and cost once a run has finished.

## Why Prediction Was Removed

`backend/api/estimates.py` held hand-maintained token constants and quoted a dollar figure on the
filters screen before anything ran. It was deleted on 2026-08-24 along with the
`estimated_input_tokens`, `estimated_output_tokens` and `estimated_cost` fields on both preview
responses.

The constants had drifted from the prompts they claimed to measure. Comparing them against the
token counts in a real Langfuse trace of one playlist run on 2026-08-24:

| Call            | Constant claimed | Provider reported |
| --------------- | ---------------- | ----------------- |
| Prompt analysis | 700              | 397               |
| Narrative       | 400              | 645               |
| Total           | 1100             | 1042              |

The total was close only because the two errors ran in opposite directions. Nothing checked either
figure, and nothing could: the constants described prompt text that lived in another module and
changed without them.

Counting characters and dividing by four was rejected: it is still an approximation, wrong by a
different margin on every prompt.

Counting with a tokenizer was rejected because a tokenizer is exact only for its own vocabulary.
MediaSage reaches any OpenAI-compatible server (`backend/llm/constants.py:13-19`), so the served
model's vocabulary is not knowable at build time, and several providers publish none. Asking the
server to tokenize is a live call, which is what a preview exists to avoid.

## What Is Still Approximate

`BudgetConfig.tokens_per_track` and `tokens_per_album` are measured averages for one library line
(`backend/config/models.py:266-276`). They feed `TokenBudget.max_tracks` and `max_albums`
(`backend/llm/models.py:41-46`), which cap how many rows enter a prompt so a large library cannot
overflow the context window.

These are the same class of guess, kept for a different job: they bound a prompt rather than quote a
figure to the user. No screen displays them, and being wrong costs a suboptimal cap rather than a
false number.

TODO(budget): decide whether the context-window cap keeps its per-item averages or is replaced.
Removing them removes overflow protection; counting the prompt exactly is not available offline for
an arbitrary OpenAI-compatible server.

## Naming

Every `estimated_cost` field on a response — `GenerateResponse`, `PlaylistCompleteFrame`,
`RecommendGenerateResponse`, and the analyze responses — carries a real figure derived from provider
counts. The name predates this decision and is now wrong. It survives because it is part of the HTTP
contract the SPA generates its types from.
