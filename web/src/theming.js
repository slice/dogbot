import { lighten, darken } from 'polished'

export const sansSerif =
  "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue', sans-serif;"
export const monospace =
  "PragmataPro, source-code-pro, Menlo, Monaco, Consolas, 'Courier New', monospace"

export const themes = {
  light: {
    name: 'light',
    bg: '#fff',
    fg: '#333',
    accent: 'hsl(270, 100%, 70%)',
    accentFg: '#fff',
    moods: {
      default: 'hsl(270, 100%, 75%)',
      danger: 'hsl(0, 100%, 75%)',
      success: 'hsl(120, 100%, 75%)',
      warning: 'hsl(50, 100%, 75%)',
    },
  },
  dark: {
    name: 'dark',
    bg: '#222',
    fg: '#ccc',
    accent: 'hsl(160, 100%, 30%)',
    accentFg: '#ddd',
    moods: {
      default: 'hsl(270, 20%, 30%)',
      danger: 'hsl(0, 20%, 30%)',
      success: 'hsl(120, 20%, 30%)',
      warning: 'hsl(50, 20%, 30%)',
    },
  },
}

export function adjust(percent, value) {
  if ([themes.light.bg, themes.light.fg].includes(value)) {
    return darken(percent, value)
  }

  return lighten(percent, value)
}
