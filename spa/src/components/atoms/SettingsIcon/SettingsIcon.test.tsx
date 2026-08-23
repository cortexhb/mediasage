import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { SettingsIcon } from './SettingsIcon.tsx'

describe('SettingsIcon', () => {
  it('adds nothing to the name of what contains it', () => {
    // Its only observable property: hidden, so the link keeps its own name.
    render(
      <button type="button">
        Settings
        <SettingsIcon />
      </button>,
    )

    expect(screen.getByRole('button', { name: 'Settings' })).toBeVisible()
  })
})
