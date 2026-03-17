import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { ErrorBanner } from '../ErrorBanner'

describe('ErrorBanner', () => {
  it('renders the error message', () => {
    render(<ErrorBanner message="Something went wrong" />)
    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(screen.getByText('Something went wrong')).toBeInTheDocument()
  })

  it('calls onDismiss when the dismiss button is clicked', async () => {
    const user = userEvent.setup()
    const onDismiss = vi.fn()
    render(<ErrorBanner message="Error" onDismiss={onDismiss} />)

    await user.click(screen.getByRole('button', { name: /dismiss/i }))
    expect(onDismiss).toHaveBeenCalledOnce()
  })

  it('does not render dismiss button when onDismiss is not provided', () => {
    render(<ErrorBanner message="Error" />)
    expect(screen.queryByRole('button', { name: /dismiss/i })).not.toBeInTheDocument()
  })

  it('applies variant-specific styles', () => {
    const { rerender } = render(<ErrorBanner message="err" variant="error" />)
    const alert = screen.getByRole('alert')
    expect(alert.className).toContain('red')

    rerender(<ErrorBanner message="warn" variant="warning" />)
    expect(screen.getByRole('alert').className).toContain('amber')

    rerender(<ErrorBanner message="info" variant="info" />)
    expect(screen.getByRole('alert').className).toContain('blue')
  })
})
