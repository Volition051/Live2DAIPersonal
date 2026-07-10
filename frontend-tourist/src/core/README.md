# Live2D 控制系统技术文档

## 📋 目录
- [架构概览](#架构概览)
- [核心模块](#核心模块)
- [使用指南](#使用指南)
- [技术规范](#技术规范)
- [常见问题](#常见问题)

---

## 架构概览

本次重构基于《Live2D控制技术文档总结.md》，采用模块化设计，将Live2D控制逻辑从Vue组件中分离出来，形成独立的核心控制器。

```
frontend-tourist/src/
├── core/
│   └── Live2DController.js    # 核心控制器（新增）
├── components/
│   └── Live2DViewers.vue      # Vue组件（已重构）
```

### 设计原则

1. **单一职责**：控制器负责所有Live2D操作，Vue组件负责UI和生命周期
2. **关注点分离**：口型同步、动作控制、表情控制各自独立
3. **易于测试**：核心逻辑可独立于Vue进行测试
4. **可扩展性**：通过配置和映射表轻松添加新功能

---

## 核心模块

### 1. Live2DController.js

#### 常量定义

```javascript
// 动作优先级
Priority.None    // 0 - 无优先级
Priority.Idle    // 1 - 待机动作（最低）
Priority.Normal  // 2 - 普通动作
Priority.Force   // 3 - 强制动作（最高）

// Viseme映射（15种音素）
VISeme_MAPPING = {
  sil: 0.0, PP: 0.25, FF: 0.25, TH: 0.45, DD: 0.45,
  CH: 0.45, SS: 0.45, nn: 0.25, kk: 0.65, E: 0.65,
  ih: 0.45, aa: 0.85, oh: 0.65, ou: 0.85
}

// 情感→表情映射
SENTIMENT_TO_EXPRESSION = {
  veryHappy: 'F04',  // ≥ 1.5
  happy: 'F01',      // ≥ 0.3
  neutral: 'F01',    // 默认
  angry: 'F02',      // ≤ -0.3
  sad: 'F03'         // ≤ -0.7
}

// 语义动作映射
ACTION_MAP = {
  nod: { group: 'TapBody', candidates: [1, 3] },
  wave: { group: 'TapBody', candidates: [10] },
  think: { group: 'TapBody', candidates: [11, 12] },
  // ... 更多动作
}
```

#### LipSync 类

口型同步器，实现平滑过渡和Viseme驱动。

```javascript
class LipSync {
  constructor(setMouthCallback)
  startLipSync(lips, elapsedTimeProvider?)
  update()  // 每帧调用
  setSmoothingFactor(factor)
  reset()
}
```

**关键特性：**
-  线性插值平滑过渡
-  支持外部时间源（audio.currentTime）
-  自动闭合（播放结束后归零）
-  可调整平滑因子（0.1~0.9）

#### Live2DController 类

统一控制器，封装所有Live2D操作。

```javascript
class Live2DController {
  constructor(model)
  
  // 参数控制
  setParameterAbsolute(paramId, value)   // 绝对设置
  addParameterRelative(paramId, delta)   // 相对添加
  
  // 口型同步
  speakWithVisemes(lipsData, audioElement?)  // Viseme驱动（推荐）
  speakWithEstimation(text)                   // 文本估算（降级）
  stopSpeaking()
  
  // 表情控制
  setExpression(expressionName)
  setExpressionBySentiment(sentiment)
  setRandomExpression()
  
  // 动作控制
  startRandomMotion(group, priority?)
  performAction(behavior, intensity?)
  
  // 交互管理
  disableEyeAndHeadTracking()  // 每帧调用
  bindClickEvents(onHeadClick, onBodyClick)
  
  // 生命周期
  update()     // 每帧调用（ticker）
  destroy()
}
```

---

## 使用指南

### 基础用法

```javascript
import { createLive2DController } from '@/core/Live2DController'

// 创建控制器
const controller = createLive2DController(model)

// 口型同步（推荐方式）
controller.speakWithVisemes(lipsData, audioElement)

// 停止说话
controller.stopSpeaking()
```

### 带情感和动作的对话

```javascript
// 后端返回的消息结构
const message = {
  text: "欢迎使用数字人系统",
  lips: [{ Lip: "aa", Time: 300 }, ...],
  sentiment: 1.2,
  action: { behavior: "wave", intensity: 0.8 }
}

// 执行对话
controller.setExpressionBySentiment(message.sentiment)
controller.performAction(message.action.behavior, message.action.intensity)
controller.speakWithVisemes(message.lips, audioElement)
```

### 手动控制

```javascript
// 设置特定表情
controller.setExpression('F04')  // 惊喜

// 播放随机动作
controller.startRandomMotion('TapBody', Priority.Normal)

// 执行语义动作
controller.performAction('nod', 1.0)    // 点头
controller.performAction('think', 0.7)  // 思考

// 直接设置参数（高级用法）
controller.setParameterAbsolute('ParamMouthOpenY', 0.5)
```

### Vue组件中的集成

```vue
<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { createLive2DController } from '@/core/Live2DController'

let controller = null

onMounted(async () => {
  const model = await Live2DModel.from(modelPath)
  controller = createLive2DController(model)
  
  // 在PixiJS ticker中更新
  app.ticker.add(() => controller.update())
})

onBeforeUnmount(() => {
  controller?.destroy()
})
</script>
```

---

## 技术规范

###  必须遵守的规则

#### 1. 参数控制区分

| 方法 | 用途 | 示例 |
|------|------|------|
| `setParameterValueById` | 绝对设置（覆盖） | 口型同步、表情切换 |
| `addParameterValueById` | 相对添加（累加） | 拖拽、呼吸、物理 |

**重要：** ParamMouthOpenY 必须使用绝对设置，防止被表情覆盖。

#### 2. 口型同步优先级

```javascript
//  正确：在 update() 中最后执行
update() {
  // 1. 更新表情（相对变化）
  this._expressionManager.update()
  
  // 2. 更新动作
  this._motionManager.update()
  
  // 3. 最后更新口型（绝对设置）
  this._lipSync.update()
}
```

#### 3. 动作优先级使用

```javascript
//  对话相关动作使用 Force 优先级
controller.startRandomMotion('TapBody', Priority.Force)

//  普通交互使用 Normal 优先级
controller.startRandomMotion('Idle', Priority.Normal)
```

#### 4. 禁用自动跟踪

```javascript
//  在每帧更新中持续调用
app.ticker.add(() => {
  controller.disableEyeAndHeadTracking()
})
```

需要重置的参数：
- ParamEyeBallX/Y（眼球）
- ParamAngleX/Y/Z（头部）
- ParamBodyAngleX/Y/Z（身体）

### ⚠️ 常见错误

```javascript
// ❌ 错误：使用相对添加设置口型
model.addParameterValueById('ParamMouthOpenY', value)

//  正确：使用绝对设置
model.setParameterValueById('ParamMouthOpenY', value)

// ❌ 错误：在表情文件中设置 ParamMouthOpenY 关键帧
//  正确：ParamMouthOpenY 留给程序独占控制

// ❌ 错误：强制中断动作
motionManager.stopAllMotions()

//  正确：让动作自然结束
motionManager.setReservePriority(Priority.None)
```

---

## 常见问题

### Q1: 口型不同步怎么办？

**原因：** 浏览器自动播放限制导致音频延迟启动。

**解决方案：**
```javascript
// 使用 audio.currentTime 作为时间源
controller.speakWithVisemes(lipsData, audioElement)
```

### Q2: 表情影响嘴型？

**原因：** 使用了 `addParameterValueById` 或表情文件中有 ParamMouthOpenY 关键帧。

**解决方案：**
```javascript
// 确保使用绝对设置
controller.setParameterAbsolute('ParamMouthOpenY', value)
```

### Q3: 动作不播放？

**原因：** 优先级不足或资源未预加载。

**解决方案：**
```javascript
// 使用 Force 优先级
controller.startRandomMotion('TapBody', Priority.Force)
```

### Q4: 如何调整口型平滑度？

```javascript
// 更快响应（适合快节奏对话）
controller.lipSync.setSmoothingFactor(0.6)

// 更平滑（适合慢速说话）
controller.lipSync.setSmoothingFactor(0.1)

// 默认值（推荐）
controller.lipSync.setSmoothingFactor(0.3)
```

### Q5: 如何添加新动作？

编辑 `ACTION_MAP`：
```javascript
export const ACTION_MAP = {
  // ... existing actions ...
  dance: { group: 'TapBody', candidates: [20, 21] }
}

// 使用
controller.performAction('dance', 1.0)
```

---

## 性能优化建议

1. **预加载资源**：模型、动作、表情在初始化时加载
2. **复用 Audio 实例**：避免频繁 GC
3. **节流日志输出**：减少控制台开销
4. **WebGL 合批绘制**：PixiJS 自动处理

---

## 技术栈版本

-  pixi.js: ^6.5.10
-  pixi-live2d-display: ^0.4.0
-  vue: ^3.5.32
-  模型格式：Cubism 4 (.model3.json)

---

## 参考资料

- [Live2D控制技术文档总结.md](../../Live2D控制技术文档总结.md)
- [OVR LipSync 官方文档](https://developer.oculus.com/documentation/unity/audio-ovrlipsync/)
- [pixi-live2d-display GitHub](https://github.com/guansss/pixi-live2d-display)

---

**文档版本：** 2.0  
**更新日期：** 2026-05-22  
**作者：** 基于技术文档重构
