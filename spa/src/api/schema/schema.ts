/**
 * The API's own OpenAPI document, which is where the settings form comes from.
 *
 * Not generated: codegen turns the schema into types, and this reads the same
 * schema as data. The `*Patch` models in it carry every editable field's type,
 * bounds and description, so the form needs no field table of its own.
 */
import { request } from '../request/request.ts'

/** Untyped on purpose: `libs/patchFields` owns what a property may look like. */
export interface OpenApiDocument {
  readonly components?: { readonly schemas?: Record<string, never> }
}

/** `GET /openapi.json` — static, and cheap enough for a loader. */
export function readSchema(signal: AbortSignal): Promise<OpenApiDocument> {
  return request<OpenApiDocument>('/openapi.json', { signal })
}
