/**
 * What an unmatched path renders, inside the shell.
 *
 * It exists from Phase 1 because the navigation links to routes that arrive
 * in later phases; without it those links fall to the router's own error
 * page, which reads as a crash rather than as a page not built yet.
 *
 * No stylesheet: it uses the document's own type and link colours.
 */
import { Link } from 'react-router'

import { Heading } from '../../components/atoms/Heading/Heading.tsx'
import { Text } from '../../components/atoms/Text/Text.tsx'

export function NotFound() {
  return (
    <>
      <Heading level={2}>Page not found</Heading>
      <Text>
        Nothing lives at this address. <Link to="/">Go home</Link>.
      </Text>
    </>
  )
}
