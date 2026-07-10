import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'

// 引入 Vant 基础样式
import 'vant/lib/index.css'

// 按需引入所有用到的 Vant 组件
import {
  NavBar,
  Button,
  Field,
  Loading,
  Collapse,
  CollapseItem,
  // 如有其他组件，继续添加
} from 'vant'

const app = createApp(App)

// 注册组件
app.use(NavBar)
app.use(Button)
app.use(Field)
app.use(Loading)
app.use(Collapse)
app.use(CollapseItem)

app.use(createPinia())
app.use(router)
app.mount('#app')