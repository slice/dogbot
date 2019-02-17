const log = (tag) => (...stuff) => {
  console.log(
    `%cdog%c [${tag}]%c`,
    'font-weight: bold; color: green;',
    'font-weight: bold; color: purple;',
    'color: inherit; font-weight: inherit',
    ...stuff
  )
}

export default log
