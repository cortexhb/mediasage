import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { StorageWarning } from './StorageWarning.tsx'

describe('StorageWarning', () => {
  it('says nothing when the directory can be written', () => {
    const { container } = render(
      <StorageWarning writable directory="/data" uid={1000} gid={1000} />,
    )

    expect(container).toBeEmptyDOMElement()
  })

  it('names the directory and the ids a chown would need', () => {
    render(
      <StorageWarning
        writable={false}
        directory="/data"
        uid={1000}
        gid={1000}
      />,
    )

    expect(screen.getByRole('alert')).toHaveTextContent(
      '/data is not writable by uid 1000, gid 1000.',
    )
  })

  it('announces it, since nothing else reports a failed write', () => {
    render(
      <StorageWarning writable={false} directory="/data" uid={1} gid={1} />,
    )

    expect(screen.getByRole('alert')).toBeVisible()
    expect(screen.getByRole('heading', { name: 'Storage' })).toBeVisible()
  })

  it('still warns when the backend reported no ids', () => {
    render(
      <StorageWarning
        writable={false}
        directory={undefined}
        uid={undefined}
        gid={undefined}
      />,
    )

    expect(screen.getByRole('alert')).toHaveTextContent(
      'The data directory is not writable by uid unknown, gid unknown.',
    )
  })

  it('reports uid 0 as zero rather than as missing', () => {
    // `uid ?? 'unknown'` is why: `||` would print root as unknown.
    render(
      <StorageWarning writable={false} directory="/data" uid={0} gid={0} />,
    )

    expect(screen.getByRole('alert')).toHaveTextContent('uid 0, gid 0')
  })
})
