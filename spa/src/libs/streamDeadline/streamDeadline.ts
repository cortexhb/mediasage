/**
 * How long a stream may be silent before the reader gives up.
 *
 * The deployment decides it, not this code: `llm.stream_idle_timeout` is a
 * `MediasageConfig` field because it varies with the hardware behind the
 * model. Read here in milliseconds, which is what `readEventStream` takes.
 *
 * A configuration that cannot be read falls back to the same default the
 * backend field carries, so a failed read never shortens the wait.
 */
import { readConfig } from '../../api/config/config.ts'

/** `LLMConfig.stream_idle_timeout` in `backend/config/models.py`. */
const DEFAULT_SECONDS = 600

export async function streamDeadline(signal: AbortSignal): Promise<number> {
  try {
    const config = await readConfig(signal)
    // The field is `gt=0`, so zero is not a value it holds.
    return (config.sections.llm.stream_idle_timeout ?? DEFAULT_SECONDS) * 1000
  } catch {
    return DEFAULT_SECONDS * 1000
  }
}
