import schema from './schema'

import yaml from 'js-yaml'

export default async function validate(yamlText) {
  const document = yaml.load(yamlText)
  await schema.validate(document, { strict: true })
}
