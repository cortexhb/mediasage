/**
 * One row of filter chips, with the heading and the Select All beside it.
 *
 * Both filters steps draw two of these -- genres and decades -- and the
 * selection is the caller's, because it is what the caller submits as hidden
 * inputs. This owns the toggling and nothing else.
 *
 * Everything selected is submitted as no filter at all; that is the action's
 * business (`libs/narrowSelection`), not this one's.
 */
import { Chip } from '../../atoms/Chip/Chip.tsx'
import { Heading } from '../../atoms/Heading/Heading.tsx'
import styles from './ChipPicker.module.scss'

/** One chip's name and, where it has one, the count it stands for. */
export interface ChipChoice {
  readonly name: string
  readonly count?: number | null | undefined
}

export interface ChipPickerProps {
  /** The heading, whose lower case is what Select All announces. */
  readonly title: string
  /** Names the group for assistive technology, e.g. "Genre filters". */
  readonly groupLabel: string
  readonly choices: readonly ChipChoice[]
  readonly selected: readonly string[]
  readonly onChange: (selected: readonly string[]) => void
}

export function ChipPicker({
  title,
  groupLabel,
  choices,
  selected,
  onChange,
}: ChipPickerProps) {
  const all = choices.map((choice) => choice.name)
  const everything = selected.length === all.length

  /** Add or remove one name, which is what a chip click means. */
  const toggle = (name: string): void => {
    onChange(
      selected.includes(name)
        ? selected.filter((each) => each !== name)
        : [...selected, name],
    )
  }

  return (
    <>
      <div className={styles.chipPicker__header}>
        <Heading level={3}>{title}</Heading>
        <button
          type="button"
          className={styles.chipPicker__toggleAll}
          aria-label={`${everything ? 'Deselect' : 'Select'} all ${title.toLowerCase()}`}
          onClick={() => {
            onChange(everything ? [] : all)
          }}
        >
          {everything ? 'Deselect All' : 'Select All'}
        </button>
      </div>
      <div
        className={styles.chipPicker__chips}
        role="group"
        aria-label={groupLabel}
      >
        {choices.map((choice) => (
          <Chip
            key={choice.name}
            selected={selected.includes(choice.name)}
            count={choice.count}
            onChoose={() => {
              toggle(choice.name)
            }}
          >
            {choice.name}
          </Chip>
        ))}
      </div>
    </>
  )
}
