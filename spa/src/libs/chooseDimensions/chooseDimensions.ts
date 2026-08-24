/**
 * What leaving the dimensions step does: keep the selection and the notes.
 *
 * Nothing is bought here. `frontend/app.js:3032` read the library stats at
 * this point; the filters step reads them itself now, so this only records
 * what was chosen and moves on.
 *
 * At least one dimension is required, as the legacy required it: with none,
 * the generation prompt says only "explore this track" and the seed's own
 * character is what it stops using.
 */
import type { ActionFunctionArgs } from 'react-router'
import { redirect } from 'react-router'

import { readPlaylistFlow, writePlaylistFlow } from '../flowStore/flowStore.ts'
import { formText } from '../formText/formText.ts'

/** What the dimensions step renders when nothing was chosen. */
export interface DimensionsActionResult {
  readonly error: string
}

export async function chooseDimensions({
  request,
}: Pick<ActionFunctionArgs, 'request'>): Promise<
  Response | DimensionsActionResult
> {
  const flow = readPlaylistFlow()
  if (flow?.mode !== 'seed') return redirect('/playlist/seed')

  const form = await request.formData()
  const selectedDimensions = form.getAll('dimensions').map(String)
  if (!selectedDimensions.length) {
    return { error: 'Please select at least one dimension' }
  }

  writePlaylistFlow({
    ...flow,
    selectedDimensions,
    notes: formText(form, 'notes').trim(),
  })
  return redirect('/playlist/seed/filters')
}
