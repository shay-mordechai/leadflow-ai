// frontend/__tests__/Navbar.test.tsx
import { render, screen } from '@testing-library/react'
import Navbar from '@/components/marketing/Navbar'

describe('Navbar Component', () => {
  it('renders the brand name correctly', () => {
    render(<Navbar />)
    
    // Check if the logo text "My-Leads" is in the document
    const brandName = screen.getByText(/My-Leads/i)
    expect(brandName).toBeInTheDocument()
  })

  it('renders login and register buttons', () => {
    render(<Navbar />)
    
    const loginLink = screen.getByRole('link', { name: /התחברות/i })
    const registerLink = screen.getByRole('link', { name: /התחל חינם/i })
    
    expect(loginLink).toBeInTheDocument()
    expect(registerLink).toBeInTheDocument()
  })
})