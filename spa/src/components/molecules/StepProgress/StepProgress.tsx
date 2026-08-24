/**
 * What a slow request is doing, as a list of named stages.
 *
 * Ports `.step-progress-item` from `frontend/app.js:4628`. A caller that
 * streams passes the stage its `progress` frames report. Without one the
 * stages are timed, as `frontend/app.js:4594` timed them for the requests
 * that answer once: they say what kind of wait this is, not how far along.
 *
 * It paces itself from the mount, so a second wait needs it unmounted in
 * between -- which is what an `Overlay` closing already does.
 */
import { useStepTicker } from '../../../libs/useStepTicker/useStepTicker.ts'
import styles from './StepProgress.module.scss'

export interface StepProgressProps {
  readonly steps: readonly string[]
  /** Which stage is running, where a stream reports it. Timed when absent. */
  readonly at?: number | undefined
}

export function StepProgress({ steps, at }: StepProgressProps) {
  const ticked = useStepTicker(steps.length)
  const current = at ?? ticked

  return (
    <ol className={styles.stepProgress}>
      {steps.map((step, index) => (
        <li
          key={step}
          className={styles.stepProgress__step}
          data-state={
            index < current ? 'done' : index === current ? 'active' : 'ahead'
          }
        >
          <span className={styles.stepProgress__mark} aria-hidden="true" />
          {step}
        </li>
      ))}
    </ol>
  )
}
