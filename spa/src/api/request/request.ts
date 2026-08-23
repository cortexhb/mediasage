/**
 * The one fetch client. Nothing outside `src/api/` calls `fetch`.
 *
 * Deliberately small: it builds a URL, sends JSON, and turns a non-2xx answer
 * into a thrown `ApiError`. Per-resource wrappers pair a generated request
 * type with its generated response type and live beside the page that needs
 * them, so this file never grows an endpoint list.
 *
 * Paths are relative. Vite proxies `/api` in development and the app is served
 * from the same origin in production, so no base URL is configured anywhere.
 */

/** What the API is asked to do. Only the verbs the backend actually serves. */
export type HttpMethod = 'GET' | 'POST' | 'PATCH' | 'DELETE'

export interface RequestOptions {
  readonly method?: HttpMethod
  /** Sent as JSON. Omitted entirely on a GET. */
  readonly body?: unknown
  /** Fills `{name}` placeholders in the url. */
  readonly path?: Readonly<Record<string, string | number>>
  /** Appended as a query string. An `undefined` value is left out. */
  readonly query?: Readonly<
    Record<string, string | number | boolean | undefined>
  >
  /**
   * Required, not optional.
   *
   * Every caller has one: a loader and an action are handed `request.signal`
   * by the router, and a component effect owns an `AbortController`. Making
   * it optional would make the leaking case the easy one.
   */
  readonly signal: AbortSignal
}

/** The API answered, and the answer was a refusal. */
export class ApiError extends Error {
  readonly status: number
  readonly body: unknown

  constructor(status: number, statusText: string, body: unknown) {
    super(ApiError.explain(body) || `${String(status)} ${statusText}`)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }

  /**
   * The readable part of a FastAPI error body.
   *
   * `detail` is a string for `HTTPException` and a list of per-field problems
   * for a 422. Anything else yields an empty string and the caller falls back
   * to the status line.
   */
  private static explain(body: unknown): string {
    if (typeof body !== 'object' || body === null) return ''
    const { detail } = body as { detail?: unknown }
    if (typeof detail === 'string') return detail
    if (!Array.isArray(detail)) return ''
    return detail
      .map((problem: unknown) => {
        if (typeof problem !== 'object' || problem === null) return ''
        const { msg } = problem as { msg?: unknown }
        return typeof msg === 'string' ? msg : ''
      })
      .filter(Boolean)
      .join('; ')
  }
}

/**
 * Send a request and return its parsed body.
 *
 * Throws `ApiError` on a non-2xx answer. An abort and a network failure are
 * left to propagate as themselves, so a caller can still tell a cancellation
 * from a server that is down.
 */
export async function request<TResult>(
  url: string,
  options: RequestOptions,
): Promise<TResult> {
  const response = await send(url, options)
  return (await parse(response)) as TResult
}

/**
 * Send a request and return its body unread, for `readEventStream`.
 *
 * A stream that never starts still answers with a status, so the same error
 * handling applies before the first frame is read.
 */
export async function stream(
  url: string,
  options: RequestOptions,
): Promise<ReadableStream<Uint8Array>> {
  const response = await send(url, options)
  if (!response.body) {
    throw new ApiError(response.status, response.statusText, {
      detail: 'The server answered without a body',
    })
  }
  return response.body
}

/** The shared half: build the request, send it, refuse a non-2xx answer. */
async function send(url: string, options: RequestOptions): Promise<Response> {
  const { method = 'GET', body, signal } = options

  const response = await fetch(address(url, options), {
    method,
    signal,
    ...(body === undefined
      ? {}
      : {
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        }),
  })

  if (!response.ok) {
    throw new ApiError(
      response.status,
      response.statusText,
      await parse(response),
    )
  }
  return response
}

/** The url with its placeholders filled and its query string appended. */
function address(url: string, options: RequestOptions): string {
  const filled = Object.entries(options.path ?? {}).reduce(
    (address_, [name, value]) =>
      address_.replace(`{${name}}`, encodeURIComponent(String(value))),
    url,
  )

  const query = new URLSearchParams()
  for (const [name, value] of Object.entries(options.query ?? {})) {
    if (value !== undefined) query.append(name, String(value))
  }

  const search = query.toString()
  return search ? `${filled}?${search}` : filled
}

/**
 * A response body as JSON, or `undefined` when there is none.
 *
 * A 204 and an error page that is not JSON both reach here, so a parse
 * failure answers `undefined` rather than masking the status that caused it.
 */
async function parse(response: Response): Promise<unknown> {
  if (response.status === 204) return undefined
  const text = await response.text()
  if (text === '') return undefined
  try {
    return JSON.parse(text) as unknown
  } catch {
    return text
  }
}
