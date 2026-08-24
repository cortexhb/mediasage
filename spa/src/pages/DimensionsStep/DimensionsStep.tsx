/**
 * Step two of the seed flow: choose what to explore about the track.
 *
 * Nothing is bought here, so the submit only records the selection and the
 * notes before the filters step. The chosen ids ride as hidden inputs, as the
 * filters step sends its chips, because the cards are not form controls.
 *
 * At least one dimension is required. The action enforces it, since a reader
 * who submits with none must be told why rather than find the button dead.
 */
import { useState } from 'react'
import { Form, useActionData, useLoaderData } from 'react-router'

import { AlbumArt } from '../../components/atoms/AlbumArt/AlbumArt.tsx'
import { Button } from '../../components/atoms/Button/Button.tsx'
import { Heading } from '../../components/atoms/Heading/Heading.tsx'
import { Label } from '../../components/atoms/Label/Label.tsx'
import { Text } from '../../components/atoms/Text/Text.tsx'
import { Textarea } from '../../components/atoms/Textarea/Textarea.tsx'
import { DimensionCard } from '../../components/molecules/DimensionCard/DimensionCard.tsx'
import { Stepper } from '../../components/molecules/Stepper/Stepper.tsx'
import type { DimensionsActionResult } from '../../libs/chooseDimensions/chooseDimensions.ts'
import type { SeedFlow } from '../../libs/flowStore/flowStore.ts'
import { playlistSteps } from '../../libs/flowSteps/flowSteps.ts'
import styles from './DimensionsStep.module.scss'

export function DimensionsStep() {
  const flow = useLoaderData<SeedFlow>()
  const failed = useActionData<DimensionsActionResult>()
  const [chosen, setChosen] = useState<readonly string[]>(
    flow.selectedDimensions ?? [],
  )

  const toggle = (id: string): void => {
    setChosen((current) =>
      current.includes(id)
        ? current.filter((one) => one !== id)
        : [...current, id],
    )
  }

  return (
    <div className={styles.dimensions}>
      <Stepper steps={playlistSteps('seed')} current={2} />

      <Heading level={2}>Choose dimensions to explore</Heading>
      <p className={styles.dimensions__description}>
        Select what aspects of this track you want more of.
      </p>

      <div className={styles.dimensions__track}>
        <AlbumArt
          src={flow.track.art_url}
          artist={flow.track.artist}
          album={flow.track.album}
          size="seed"
        />
        <div className={styles.dimensions__info}>
          <div className={styles.dimensions__title}>{flow.track.title}</div>
          <div className={styles.dimensions__artist}>
            {flow.track.artist} - {flow.track.album}
          </div>
        </div>
      </div>

      <Form method="post">
        {chosen.map((id) => (
          <input key={id} type="hidden" name="dimensions" value={id} />
        ))}

        <div
          className={styles.dimensions__list}
          role="group"
          aria-label="Available dimensions"
        >
          {flow.dimensions.map((dimension) => (
            <DimensionCard
              key={dimension.id}
              dimension={dimension}
              selected={chosen.includes(dimension.id)}
              onToggle={() => {
                toggle(dimension.id)
              }}
            />
          ))}
        </div>

        {failed && (
          <Text tone="error" role="alert">
            {failed.error}
          </Text>
        )}

        <div className={styles.dimensions__notes}>
          <Label htmlFor="notes" optional>
            Additional notes
          </Label>
          <Textarea
            id="notes"
            name="notes"
            rows={2}
            defaultValue={flow.notes ?? ''}
            placeholder="Any additional preferences..."
          />
        </div>

        <Button type="submit" variant="primary">
          Continue to Filters
        </Button>
      </Form>
    </div>
  )
}
