/**
 * The id a flow's LLM calls are grouped under.
 *
 * Both flows mint one, which is why it lives beside neither store. It reaches
 * the backend as `flow_id` and becomes the Langfuse session, so every call a
 * single run of the wizard makes is one trace group.
 */

/**
 * An id for a flow about to start.
 *
 * `crypto.randomUUID` is secure-context only, and MediaSage is normally
 * reached over plain HTTP on a LAN, where it is undefined. `getRandomValues`
 * carries no such restriction.
 */
export function newFlowId(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16))
  return [...bytes].map((byte) => byte.toString(16).padStart(2, '0')).join('')
}
