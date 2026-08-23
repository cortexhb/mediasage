/**
 * A titled card of settings.
 *
 * The heading is `atoms/Heading` at level 3, which is what a `section` under
 * the page's `h2` should carry.
 */
import { Heading } from '../../atoms/Heading/Heading.tsx'
import styles from './Section.module.scss'

export interface SectionProps {
  readonly title: string
  readonly children: React.ReactNode
}

export function Section({ title, children }: SectionProps) {
  return (
    <section className={styles.section}>
      <Heading level={3}>{title}</Heading>
      {children}
    </section>
  )
}
