/**
 * A heading at a chosen level.
 *
 * The level is the document outline, not a size: an `h2` under an `h1` is
 * what a screen reader navigates by. Size comes from `data-level`, which the
 * stylesheet selects on, so a section can restyle without changing the
 * outline.
 */
import styles from './Heading.module.scss'

export interface HeadingProps {
  readonly level: 1 | 2 | 3
  readonly children: React.ReactNode
}

export function Heading({ level, children }: HeadingProps) {
  const Tag = `h${String(level)}` as 'h1' | 'h2' | 'h3'

  return (
    <Tag className={styles.heading} data-level={level}>
      {children}
    </Tag>
  )
}
