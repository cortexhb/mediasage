/**
 * The readable part of whatever a route threw.
 *
 * A thrown `Response` is the router's own shape and carries no `message`, so
 * it is read separately from an `Error`. Anything else reached the boundary
 * without saying what it was.
 */
import { isRouteErrorResponse } from 'react-router'

export function explainError(error: unknown): string {
  if (isRouteErrorResponse(error)) {
    return `${String(error.status)} ${error.statusText}`
  }
  if (error instanceof Error) return error.message
  return 'The page could not be loaded.'
}
