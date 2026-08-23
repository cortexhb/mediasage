/**
 * What renders when a loader, an action, or a render throws.
 *
 * Registered on the shell, so the header stays and a failed page is
 * recoverable without the back button. It arrives with the first loader:
 * before one existed there was nothing to catch.
 */
import { useRouteError } from 'react-router'

import { Heading } from '../../components/atoms/Heading/Heading.tsx'
import { Text } from '../../components/atoms/Text/Text.tsx'
import { explainError } from '../../libs/explainError/explainError.ts'

export function ErrorPage() {
  const error = useRouteError()

  return (
    <>
      <Heading level={2}>Something went wrong</Heading>
      <Text tone="error" role="alert">
        {explainError(error)}
      </Text>
      <Text tone="muted">Reload the page, or check that the API is up.</Text>
    </>
  )
}
