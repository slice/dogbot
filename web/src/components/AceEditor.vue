<template>
  <div class="editor"></div>
</template>

<script>
import ace from 'brace'

export default {
  props: {
    content: { type: String, required: true },
    lang: { type: String, required: true },
    theme: { type: String, required: true }
  },
  data () {
    return {
      editor: null
    }
  },
  mounted () {
    let editor = ace.edit(this.$el)
    this.editor = editor
    editor.setValue(this.content)
    editor.setTheme('ace/theme/' + this.theme)

    editor.commands.addCommand({
      name: 'save',
      bindKey: { win: 'Ctrl-S', mac: 'Command-S', sender: 'editor|cli' },
      exec: editor => {
        this.$emit('save', editor.getValue())
      }
    })

    editor.on('change', () => {
      this.$emit('change', editor.getValue())
    })

    let session = editor.getSession()
    session.setOptions({
      mode: `ace/mode/${this.lang}`,
      tabSize: 4,
      useSoftTabs: true
    })
  },
  watch: {
    content (newContent) {
      this.editor.setValue(newContent)
    }
  }
}
</script>
