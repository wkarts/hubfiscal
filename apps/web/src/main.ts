import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './styles.css'
import './resource-management.css'
import './operational-console.css'

createApp(App).use(createPinia()).use(router).mount('#app')
