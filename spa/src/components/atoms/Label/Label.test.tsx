import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Label } from './Label.tsx'

describe('Label', () => {
  it('names the control it points at', () => {
    render(
      <>
        <Label htmlFor="url">Plex Server URL</Label>
        <input id="url" />
      </>,
    )

    expect(screen.getByLabelText('Plex Server URL')).toBeVisible()
  })

  it('marks an optional value in the name', () => {
    render(
      <>
        <Label htmlFor="key" optional>
          API Key
        </Label>
        <input id="key" />
      </>,
    )

    expect(screen.getByLabelText('API Key (optional)')).toBeVisible()
  })

  it('leaves a required value unmarked', () => {
    render(
      <>
        <Label htmlFor="key">API Key</Label>
        <input id="key" />
      </>,
    )

    expect(screen.getByLabelText('API Key')).toBeVisible()
  })
})
