import Vue from 'vue'
import Router from 'vue-router'
import Home from './views/Home.vue'
import EditGuild from './views/EditGuild.vue'

Vue.use(Router)

export default new Router({
  routes: [
    { path: '/', name: 'home', component: Home },
    { path: '/guild/:id', name: 'edit_guild', component: EditGuild }
  ]
})
