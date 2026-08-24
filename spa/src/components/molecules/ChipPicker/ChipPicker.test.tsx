import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'

import { ChipPicker } from './ChipPicker.tsx'

const CHOICES = [
  { name: 'Rock', count: 12 },
  { name: 'Jazz', count: 3 },
  { name: 'Folk', count: 7 },
]

/** The picker with its selection held, as the filters steps hold it. */
function Picking({ start }: { readonly start: readonly string[] }) {
  const [selected, setSelected] = useState(start)

  return (
    <>
      <ChipPicker
        title="Genres"
        groupLabel="Genre filters"
        choices={CHOICES}
        selected={selected}
        onChange={setSelected}
      />
      <p>chosen: {selected.join(',')}</p>
    </>
  )
}

describe('ChipPicker', () => {
  it('marks the selected chips, and no others', () => {
    render(<Picking start={['Jazz']} />)

    expect(screen.getByRole('button', { name: /Jazz/ })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(screen.getByRole('button', { name: /Rock/ })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
  })

  it('adds a chip that was not chosen, and removes one that was', async () => {
    render(<Picking start={['Jazz']} />)

    await userEvent.click(screen.getByRole('button', { name: /Rock/ }))
    expect(screen.getByText('chosen: Jazz,Rock')).toBeVisible()

    await userEvent.click(screen.getByRole('button', { name: /Jazz/ }))
    expect(screen.getByText('chosen: Rock')).toBeVisible()
  })

  it('offers Select All until everything is chosen, then Deselect All', async () => {
    render(<Picking start={['Jazz']} />)

    await userEvent.click(
      screen.getByRole('button', { name: 'Select all genres' }),
    )
    expect(screen.getByText('chosen: Rock,Jazz,Folk')).toBeVisible()

    const deselect = screen.getByRole('button', { name: 'Deselect all genres' })
    expect(deselect).toHaveTextContent('Deselect All')

    await userEvent.click(deselect)
    expect(screen.getByText('chosen:')).toBeVisible()
  })

  it('names the group, so the chips are announced as one set', () => {
    render(<Picking start={[]} />)

    expect(screen.getByRole('group', { name: 'Genre filters' })).toBeVisible()
  })
})
