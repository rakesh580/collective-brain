import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { LoadingSpinner } from '../LoadingSpinner'

describe('LoadingSpinner', () => {
  it('renders with default props', () => {
    render(<LoadingSpinner />)
    const spinner = screen.getByRole('status')
    expect(spinner).toBeInTheDocument()
    expect(spinner).toHaveAttribute('aria-label', 'Loading')
  })

  it('applies the correct size classes', () => {
    const { rerender } = render(<LoadingSpinner size="sm" />)
    expect(screen.getByRole('status')).toHaveClass('w-4', 'h-4')

    rerender(<LoadingSpinner size="lg" />)
    expect(screen.getByRole('status')).toHaveClass('w-12', 'h-12')
  })

  it('shows the label text when provided', () => {
    render(<LoadingSpinner label="Fetching data..." />)
    expect(screen.getByText('Fetching data...')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveAttribute('aria-label', 'Fetching data...')
  })

  it('does not render label text when label is omitted', () => {
    const { container } = render(<LoadingSpinner />)
    expect(container.querySelector('span')).toBeNull()
  })
})
