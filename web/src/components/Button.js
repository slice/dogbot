import styled from 'styled-components'

const Button = styled.button`
  font-size: 1.5rem;
  border: 0;
  background: var(--primary);
  color: var(--text-bg);
  border-radius: 0.15rem;
  padding: 0.5em 1em;
  cursor: pointer;

  &:active {
    background: var(--focus-darker);
    outline: none;
  }

  &:focus {
    outline: none;
    box-shadow: 0 0 0 5px var(--focus);
  }

  &[disabled] {
    opacity: 0.5;
    cursor: not-allowed;
  }
`

export default Button
