# Live2D 控制系统 - 文档索引

欢迎使用重构后的 Live2D 控制系统！本索引帮助你快速找到所需文档。

---

## 📖 文档导航

### 🚀 新手入门

| 文档 | 说明 | 适合人群 |
|------|------|----------|
| [QUICKSTART.md](./QUICKSTART.md) | 5分钟快速上手指南 | 首次使用者 |
| [README.md](./README.md) | 完整技术文档和API参考 | 开发者 |

### 🔄 迁移与升级

| 文档 | 说明 | 适合人群 |
|------|------|----------|
| [MIGRATION.md](./MIGRATION.md) | 从旧版本迁移指南 | 现有项目维护者 |
| [REFACTOR_SUMMARY.md](./REFACTOR_SUMMARY.md) | 重构工作总结 | 技术负责人 |

### 🧪 测试与调试

| 文件 | 说明 | 使用方法 |
|------|------|----------|
| [test-controller.js](./test-controller.js) | 控制器功能测试脚本 | 在浏览器控制台执行 |

### 📋 源代码

| 文件 | 说明 |
|------|------|
| [Live2DController.js](./Live2DController.js) | 核心控制器源码 |

---

## 🎯 根据需求选择文档

### 我是... 

#### 👨‍💻 新开发者
→ 阅读 [QUICKSTART.md](./QUICKSTART.md) 快速开始  
→ 然后查看 [README.md](./README.md) 了解完整 API

#### 🔧 项目维护者
→ 阅读 [MIGRATION.md](./MIGRATION.md) 了解变更点  
→ 运行 [test-controller.js](./test-controller.js) 验证功能

#### 📊 技术评审
→ 阅读 [REFACTOR_SUMMARY.md](./REFACTOR_SUMMARY.md) 了解架构设计  
→ 查看 [Live2DController.js](./Live2DController.js) 审查代码质量

#### 🐛 遇到问题
→ 查看 [README.md](./README.md) 的"常见问题"章节  
→ 运行 [test-controller.js](./test-controller.js) 诊断问题

---

## 📂 文件结构

```
frontend-tourist/src/core/
├── README.md                  # 完整技术文档 ⭐
├── QUICKSTART.md              # 快速开始指南
├── MIGRATION.md               # 迁移指南
├── REFACTOR_SUMMARY.md        # 重构总结
├── test-controller.js         # 测试脚本
├── Live2DController.js        # 核心控制器源码
└── INDEX.md                   # 本文档
```

---

## 🔑 核心概念速览

### 1. 控制器架构

```
Live2DController (统一入口)
├── LipSync (口型同步器)
├── 参数控制 (绝对/相对)
├── 表情管理 (直接/情感驱动)
└── 动作控制 (优先级/语义映射)
```

### 2. 关键 API

```javascript
// 创建控制器
const controller = createLive2DController(model)

// 口型同步
controller.speakWithVisemes(lipsData, audioElement)

// 表情控制
controller.setExpressionBySentiment(1.2)

// 动作执行
controller.performAction('wave', 0.8)

// 每帧更新
app.ticker.add(() => controller.update())
```

### 3. 技术规范

-  使用 `setParameterValueById` 控制口型（绝对设置）
-  在 `update()` 中最后执行 `lipSync.update()`
-  对话动作使用 `Priority.Force`
-  禁用眼球/头部/身体跟踪（每帧重置）

---

## 💡 快速链接

### 常用操作

- [如何让人物说话？](./QUICKSTART.md#场景1-让角色说话带口型)
- [如何改变表情？](./QUICKSTART.md#场景2-改变表情)
- [如何执行动作？](./QUICKSTART.md#场景3-执行动作)
- [完整对话流程？](./QUICKSTART.md#场景4-完整对话流程)

### 深入学习

- [参数控制详解](./README.md#1-参数控制系统)
- [口型同步原理](./README.md#2-口型同步技术实现)
- [动作优先级规则](./README.md#3-动作控制系统)
- [表情控制方法](./README.md#4-表情控制系统)

### 问题解决

- [口型不同步怎么办？](./README.md#q1-口型不同步怎么办)
- [表情影响嘴型？](./README.md#q2-表情影响嘴型)
- [动作不播放？](./README.md#q3-动作不播放)
- [如何调整平滑度？](./README.md#q4-如何调整口型平滑度)

---

## 📞 获取帮助

### 文档资源

1. **完整 API 文档** → [README.md](./README.md)
2. **迁移指南** → [MIGRATION.md](./MIGRATION.md)
3. **技术规范** → `../../Live2D控制技术文档总结.md`

### 调试工具

```javascript
// 访问控制器实例
window.__live2d.controller

// 查看所有可用方法
Object.keys(window.__live2d)

// 运行自动化测试
// 复制 test-controller.js 内容到控制台执行
```

### 技术支持

- 📧 技术问题：查阅文档中的联系方式
- 🐛 Bug报告：提交 Issue
- 💡 功能建议：提交 Feature Request

---

## 🎓 学习路径推荐

### 第1天：基础使用
-  阅读 [QUICKSTART.md](./QUICKSTART.md)
-  在控制台中尝试基础 API
-  运行 [test-controller.js](./test-controller.js)

### 第2天：深入理解
-  阅读 [README.md](./README.md) 的核心模块章节
-  理解参数控制区分（绝对 vs 相对）
-  掌握口型同步原理

### 第3天：高级应用
-  学习语义动作映射
-  自定义 Viseme 映射
-  调整平滑因子优化效果

### 第4天：项目集成
-  阅读 [MIGRATION.md](./MIGRATION.md)（如适用）
-  在实际项目中应用
-  性能优化和错误处理

---

## 📊 文档统计

| 文档 | 大小 | 最后更新 |
|------|------|----------|
| README.md | 8.3 KB | 2026-05-22 |
| QUICKSTART.md | 6.5 KB | 2026-05-22 |
| MIGRATION.md | 10.1 KB | 2026-05-22 |
| REFACTOR_SUMMARY.md | 11.7 KB | 2026-05-22 |
| test-controller.js | 5.2 KB | 2026-05-22 |
| Live2DController.js | 14.4 KB | 2026-05-22 |

**总计：** ~56 KB 文档和代码

---

## ✨ 特色功能

### 🎯 模块化设计
- 核心逻辑独立于 Vue 组件
- 易于测试和维护
- 可复用于其他项目

### 📚 完整文档
- 详细的技术文档
- 丰富的代码示例
- 常见问题解答

### 🔄 向后兼容
- 原有 API 保持不变
- 无缝升级，无需修改现有代码
- 渐进式采用新功能

### 🚀 高性能
- 无额外性能开销
- 优化的渲染循环
- 合理的内存管理

---

## 🎉 开始使用

选择一个文档开始阅读吧：

- 🆕 **新手** → [QUICKSTART.md](./QUICKSTART.md)
- 📖 **开发者** → [README.md](./README.md)
- 🔄 **迁移者** → [MIGRATION.md](./MIGRATION.md)
- 📊 **评审者** → [REFACTOR_SUMMARY.md](./REFACTOR_SUMMARY.md)

---

**祝你使用愉快！** 🚀

如有任何问题，请参考相应文档或联系开发团队。

---

*文档版本：1.0*  
*更新日期：2026-05-22*  
*维护者：Live2D 控制系统开发团队*
