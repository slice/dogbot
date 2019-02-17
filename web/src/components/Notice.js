import styled from 'styled-components'
import { lighten } from 'polished'

const Notice = styled.div`
  padding: 0.5em 1em;
  color: ${(props) => props.theme.fg};
  border: solid 1px
    ${(props) =>
      props.theme.name === 'dark'
        ? lighten(0.1, props.theme.moods[props.mood])
        : props.theme.moods[props.mood]};
  background: ${(props) =>
    props.theme.name === 'light'
      ? lighten(0.2, props.theme.moods[props.mood])
      : props.theme.moods[props.mood]};
  border-radius: 0.15rem;
  margin: 1rem 0;
`

export default Notice
