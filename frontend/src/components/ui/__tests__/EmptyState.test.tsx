import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { EmptyState } from '../EmptyState'

describe('EmptyState', () => {
  it('renders the title', () => {
    render(<EmptyState title="No results found" />)
    expect(screen.getByText('No results found')).toBeInTheDocument()
  })

  it('renders the description when provided', () => {
    render(<EmptyState title="Empty" description="Try adjusting your filters" />)
    expect(screen.getByText('Try adjusting your filters')).toBeInTheDocument()
  })

  it('does not render description when omitted', () => {
    const { container } = render(<EmptyState title="Empty" />)
    expect(container.querySelectorAll('p')).toHaveLength(0)
  })

  it('renders an action button and fires onClick', async () => {
    const user = userEvent.setup()
    const onClick = vi.fn()
    render(
      <EmptyState
        title="No items"
        action={{ label: 'Create new', onClick }}
      />
    )

    const button = screen.getByRole('button', { name: 'Create new' })
    expect(button).toBeInTheDocument()
    await user.click(button)
    expect(onClick).toHaveBeenCalledOnce()
  })

  it('does not render action button when action is omitted', () => {
    render(<EmptyState title="Empty" />)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
