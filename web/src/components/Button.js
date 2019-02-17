import styled from 'styled-components'
import { darken } from 'polished'

const Button = styled.button`
  font-size: 1.5rem;
  border: 0;
  background: ${(props) => props.theme.accent};
  color: ${(props) => props.theme.accentFg};
  border-radius: 0.15rem;
  padding: 0.5em 1em;
  cursor: pointer;

  &:active {
    background: ${(props) => darken(0.05, props.theme.accent)};
    outline: none;
  }

  &[disabled] {
    opacity: 0.5;
    cursor: not-allowed;
  }
`

export default Button
