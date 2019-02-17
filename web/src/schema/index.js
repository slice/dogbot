import schema from './schema'

import yaml from 'js-yaml'

export default async function validate(yamlText) {
  const document = yaml.safeLoad(yamlText)
  await schema.validate(document, { strict: true })
}
