import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { LibraryField } from './LibraryField.tsx'

describe('LibraryField', () => {
  describe('when Plex has listed its libraries', () => {
    it('offers them rather than asking for a typed name', () => {
      render(<LibraryField value="Music" libraries={['Music', 'Vinyl']} />)

      const select = screen.getByRole('combobox', { name: 'Music Library' })
      expect(select).toHaveValue('Music')
      expect(screen.getByRole('option', { name: 'Vinyl' })).toBeInTheDocument()
    })

    it('posts under the name the API reads', () => {
      render(<LibraryField value="Music" libraries={['Music']} />)

      expect(screen.getByRole('combobox')).toHaveAttribute(
        'name',
        'music_library',
      )
    })
  })

  describe('when no server has been connected', () => {
    it('falls back to free text, since there is nothing to choose from', () => {
      render(<LibraryField value="Music" libraries={[]} />)

      expect(
        screen.getByRole('textbox', { name: 'Music Library' }),
      ).toHaveValue('Music')
      expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
    })

    it('says how to get the list, since a typo reads as an empty library', () => {
      render(<LibraryField value="" libraries={[]} />)

      expect(
        screen.getByRole('textbox', { name: 'Music Library' }),
      ).toHaveAccessibleDescription(
        'Connect to Plex to choose from the libraries it offers.',
      )
    })
  })
})
