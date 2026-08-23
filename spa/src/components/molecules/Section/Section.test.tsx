import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Section } from './Section.tsx'

describe('Section', () => {
  it('titles itself at level 3, under the page heading', () => {
    render(<Section title="Plex Connection">{null}</Section>)

    expect(
      screen.getByRole('heading', { level: 3, name: 'Plex Connection' }),
    ).toBeVisible()
  })

  it('shows what it was given', () => {
    render(
      <Section title="Storage">
        <p>Not writable</p>
      </Section>,
    )

    expect(screen.getByText('Not writable')).toBeVisible()
  })
})
