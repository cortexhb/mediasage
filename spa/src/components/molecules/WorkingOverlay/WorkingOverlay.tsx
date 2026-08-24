/**
 * The wait every step of every flow puts in front of the reader.
 *
 * Six pages drew this by hand before it existed, each with its own `watching`
 * state and its own copy of the same four CSS declarations. Only two things
 * ever varied: what the wait is called, and whether the stages are reported by
 * a stream or timed.
 *
 * It cannot be dismissed, which is the legacy contract restored. Closing never
 * cancelled the work -- the stream lives in `libs/playlistRun`, outside React
 * -- so a dismissed overlay left a paid generation running with nothing on
 * screen to say so.
 *
 * A molecule despite wrapping one: it knows nothing about playlists or albums,
 * which is what puts a component in `organisms/`.
 */
import { Heading } from '../../atoms/Heading/Heading.tsx'
import { Overlay } from '../../atoms/Overlay/Overlay.tsx'
import { StepProgress } from '../StepProgress/StepProgress.tsx'
import styles from './WorkingOverlay.module.scss'

export interface WorkingOverlayProps {
  readonly open: boolean
  /** Names the wait for assistive technology, and for `titled`. */
  readonly label: string
  readonly steps: readonly string[]
  /** Which stage is running, where a stream reports it. Timed when absent. */
  readonly at?: number | undefined
  /**
   * Draw the label as a heading too.
   *
   * The step pages do; the two results pages do not, because the page behind
   * them already says what it is.
   */
  readonly titled?: boolean
}

export function WorkingOverlay({
  open,
  label,
  steps,
  at,
  titled,
}: WorkingOverlayProps) {
  return (
    <Overlay open={open} label={label} sticky>
      <div className={styles.workingOverlay}>
        {titled && <Heading level={2}>{label}</Heading>}
        <StepProgress steps={steps} at={at} />
      </div>
    </Overlay>
  )
}
