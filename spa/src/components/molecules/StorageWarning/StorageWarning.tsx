/**
 * The one diagnostic for a data directory the process cannot write.
 *
 * It lived only in the setup wizard. Without it a failed write is invisible
 * until something silently stops persisting, and the uid and gid are what
 * turn "it does not work" into a `chown`.
 */
import { Text } from '../../atoms/Text/Text.tsx'
import { Section } from '../Section/Section.tsx'

export interface StorageWarningProps {
  readonly writable: boolean
  readonly directory: string | undefined
  readonly uid: number | undefined
  readonly gid: number | undefined
}

export function StorageWarning({
  writable,
  directory,
  uid,
  gid,
}: StorageWarningProps) {
  if (writable) return null

  return (
    <Section title="Storage">
      <Text tone="error" role="alert">
        {directory ?? 'The data directory'} is not writable by uid{' '}
        {uid ?? 'unknown'}, gid {gid ?? 'unknown'}. Nothing will be saved until
        it is.
      </Text>
    </Section>
  )
}
