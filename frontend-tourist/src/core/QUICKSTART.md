# Live2D 控制系统 - 快速开始指南

## 🚀 5分钟快速上手

### 1️⃣ 启动项目

```bash
# 终端1: 启动后端
cd backend
python -m uvicorn app.main:app --reload

# 终端2: 启动游客端前端
cd frontend-tourist
npm run dev
```

### 2️⃣ 访问页面

打开浏览器访问：`http://localhost:5173`（或实际端口）

### 3️⃣ 验证控制器

打开浏览器控制台（F12），输入：

```javascript
// 检查控制器是否存在
window.__live2d.controller
```

如果看到控制器对象，说明初始化成功！

---

## 💡 基础用法

### 场景1: 让角色说话（带口型）

```javascript
const controller = window.__live2d.controller

// 方式1: 文本估算（简单，但精度较低）
controller.speakWithEstimation("你好，欢迎使用数字人系统")

// 方式2: Viseme驱动（推荐，需要后端提供数据）
const lipsData = [
  { Lip: 'sil', Time: 100 },
  { Lip: 'aa', Time: 200 },
  { Lip: 'PP', Time: 150 },
  { Lip: 'sil', Time: 100 }
]
controller.speakWithVisemes(lipsData)
```

### 场景2: 改变表情

```javascript
// 直接设置表情
controller.setExpression('F04')  // 惊喜

// 根据情感值自动选择表情
controller.setExpressionBySentiment(1.2)  // 开心 → F01
controller.setExpressionBySentiment(-0.8) // 悲伤 → F03

// 随机表情
controller.setRandomExpression()
```

### 场景3: 执行动作

```javascript
// 语义动作（推荐）
controller.performAction('wave', 0.8)    // 挥手
controller.performAction('nod', 1.0)     // 点头
controller.performAction('think', 0.7)   // 思考

// 随机动作
controller.startRandomMotion('TapBody', 2)
```

### 场景4: 完整对话流程

```javascript
// 模拟后端返回的消息
const message = {
  text: "很高兴见到你！",
  lips: [{ Lip: 'aa', Time: 200 }, ...],  // 从后端获取
  sentiment: 1.5,                          // 非常开心
  action: { behavior: 'wave', intensity: 0.8 }
}

// 执行对话
controller.setExpressionBySentiment(message.sentiment)
controller.performAction(message.action.behavior, message.action.intensity)
controller.speakWithVisemes(message.lips, audioElement)
```

---

## 🎮 交互式测试

### 在控制台中尝试

```javascript
const ctrl = window.__live2d.controller

// 测试1: 切换表情
ctrl.setExpression('F01')  // 微笑
setTimeout(() => ctrl.setExpression('F02'), 1000)  // 生气
setTimeout(() => ctrl.setExpression('F03'), 2000)  // 悲伤
setTimeout(() => ctrl.setExpression('F04'), 3000)  // 惊喜

// 测试2: 执行动作
ctrl.performAction('wave', 1.0)
setTimeout(() => ctrl.performAction('nod', 1.0), 1500)
setTimeout(() => ctrl.performAction('think', 0.8), 3000)

// 测试3: 口型同步
ctrl.speakWithEstimation("这是一段测试语音，看看口型是否同步")

// 测试4: 调整平滑度
ctrl.lipSync.setSmoothingFactor(0.1)  // 很平滑
// 或
ctrl.lipSync.setSmoothingFactor(0.9)  // 很快响应
```

---

## 📚 常用 API 速查

### 口型同步

| 方法 | 参数 | 说明 |
|------|------|------|
| `speakWithEstimation(text)` | text: string | 文本估算模式 |
| `speakWithVisemes(lips, audio?)` | lips: Array, audio?: HTMLAudioElement | Viseme驱动模式 |
| `stopSpeaking()` | - | 停止说话 |

### 表情控制

| 方法 | 参数 | 说明 |
|------|------|------|
| `setExpression(name)` | name: 'F01'~'F08' | 设置特定表情 |
| `setExpressionBySentiment(value)` | value: -2~2 | 根据情感值设置 |
| `setRandomExpression()` | - | 随机表情 |

### 动作控制

| 方法 | 参数 | 说明 |
|------|------|------|
| `performAction(behavior, intensity?)` | behavior: string, intensity?: 0-1 | 执行语义动作 |
| `startRandomMotion(group, priority?)` | group: string, priority?: 0-3 | 随机动作 |

### 高级功能

| 方法 | 参数 | 说明 |
|------|------|------|
| `setParameterAbsolute(id, value)` | id: string, value: 0-1 | 绝对设置参数 |
| `lipSync.setSmoothingFactor(factor)` | factor: 0-1 | 调整口型平滑度 |
| `bindClickEvents(onHead, onBody)` | callbacks | 绑定点击事件 |

---

## 🔧 常见问题

### Q1: 控制器未初始化？

**检查：**
```javascript
// 确认组件已挂载
console.log(window.__live2d)

// 如果为 undefined，等待页面加载完成
```

**解决：** 确保 Live2DViewers 组件已正确渲染

### Q2: 口型不动？

**检查：**
```javascript
// 确认正在说话
console.log(controller.isSpeaking)

// 手动测试口型
controller.setParameterAbsolute('ParamMouthOpenY', 0.5)
```

**可能原因：**
- 没有调用 `speakWithVisemes` 或 `speakWithEstimation`
- Viseme 数据为空

### Q3: 表情没变化？

**检查：**
```javascript
// 确认表情名称正确
controller.setExpression('F01')  // 不是 'F1'

// 查看可用表情
console.log(controller.model.internalModel.expressionManager)
```

### Q4: 动作不播放？

**检查：**
```javascript
// 确认动作组名称正确
controller.startRandomMotion('TapBody', 2)

// 尝试 Force 优先级
controller.startRandomMotion('TapBody', 3)  // Priority.Force
```

---

## 🎯 下一步

### 学习更多

1. 📖 阅读完整文档：`frontend-tourist/src/core/README.md`
2. 🔄 了解迁移：`frontend-tourist/src/core/MIGRATION.md`
3. 📊 查看总结：`frontend-tourist/src/core/REFACTOR_SUMMARY.md`

### 运行测试

```javascript
// 在浏览器控制台中
// 复制 frontend-tourist/src/core/test-controller.js 的内容并执行
```

### 自定义开发

```javascript
// 添加新动作映射
import { ACTION_MAP } from '@/core/Live2DController'

ACTION_MAP.dance = { 
  group: 'TapBody', 
  candidates: [20, 21] 
}

// 使用新动作
controller.performAction('dance', 1.0)
```

---

## 🆘 需要帮助？

1. **查阅文档** - README.md 包含完整 API 说明
2. **运行测试** - test-controller.js 演示所有功能
3. **检查控制台** - 查看错误信息和日志

---

**祝你使用愉快！** 🎉

如有问题，请参考完整技术文档或联系开发团队。
