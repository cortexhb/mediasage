/**
 * A button.
 *
 * `type` defaults to `button`. The HTML default is `submit`, which inside a
 * form makes every unmarked button post it — the mistake the legacy markup
 * avoided by writing `type` on all of them.
 */
import type { ComponentProps } from 'react'

import styles from './Button.module.scss'

// `ComponentProps`, not `…WithoutRef`: React 19 passes `ref` as a prop, and
// the nav's disclosure needs one to restore focus.
type NativeProps = Omit<ComponentProps<'button'>, 'className'>

export interface ButtonProps extends NativeProps {
  readonly variant: 'primary' | 'secondary' | 'ghost' | 'link' | 'nav'
}

export function Button({ variant, type = 'button', ...native }: ButtonProps) {
  return (
    <button
      {...native}
      type={type}
      className={styles.button}
      data-variant={variant}
    />
  )
}
