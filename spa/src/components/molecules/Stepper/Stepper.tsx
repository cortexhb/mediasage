/**
 * Where the reader is in a multi-step flow.
 *
 * `frontend/index.html:224` drew six steps and hid the ones the current mode
 * did not use, so the numbering jumped -- both step 2s existed in the markup.
 * Here each flow passes only its own steps and the numbers are the positions.
 *
 * A step is not a link. The steps behind carry state the loader would have to
 * re-derive, and the ones ahead have preconditions; navigation is the flow's
 * own buttons and the browser's back.
 *
 * The connectors are list items of their own, hidden from assistive
 * technology. Nested inside a step they took their length from that step's
 * label, so no two came out the same width.
 */
import { Fragment } from 'react'

import styles from './Stepper.module.scss'

export interface StepperProps {
  readonly steps: readonly string[]
  /** Which step is on screen, counted from 1. */
  readonly current: number
}

export function Stepper({ steps, current }: StepperProps) {
  return (
    <ol className={styles.stepper} aria-label="Progress">
      {steps.map((step, index) => {
        const position = index + 1

        return (
          <Fragment key={step}>
            {index > 0 && (
              <li
                className={styles.stepper__connector}
                data-state={position <= current ? 'done' : 'ahead'}
                aria-hidden="true"
              />
            )}
            <li
              className={styles.stepper__step}
              data-state={
                position === current
                  ? 'current'
                  : position < current
                    ? 'done'
                    : 'ahead'
              }
              aria-current={position === current ? 'step' : undefined}
            >
              <span className={styles.stepper__number}>{position}</span>
              <span className={styles.stepper__label}>{step}</span>
            </li>
          </Fragment>
        )
      })}
    </ol>
  )
}
