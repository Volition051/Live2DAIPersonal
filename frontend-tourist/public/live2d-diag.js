// =====================================================
// Live2D 控制台诊断脚本
// 在 http://localhost:3001/live2d-test 按 F12 打开控制台
// 粘贴全部代码后回车运行
// =====================================================
(async () => {

// 1. 获取模型引用
const model = window.__model
if (!model) { console.error('❌ 未找到模型，请等页面加载完再运行'); return }

const coreModel = model.internalModel?.coreModel
if (!coreModel) { console.error('❌ coreModel 不可用'); return }

console.log('✅ 模型获取成功\n')

// =====================================================
// PART 1: 参数 ID 发现
// =====================================================
console.log('===== PART 1: 参数 ID 发现 =====')

// Cubism 5 常见参数 ID 列表（Haru/通用模型）
const KNOWN_PARAMS = [
  // 身体/角度
  'ParamAngleX', 'ParamAngleY', 'ParamAngleZ',
  'ParamBodyAngleX', 'ParamBodyAngleY', 'ParamBodyAngleZ',
  // 眼球
  'ParamEyeBallX', 'ParamEyeBallY',
  'ParamEyeLOpen', 'ParamEyeROpen',
  // 口型
  'ParamMouthOpenY', 'ParamMouthForm',
  // 手臂（常见命名）
  'ParamArmLAngle', 'ParamArmRAngle',
  'ParamArmL', 'ParamArmR',
  'ParamHandL', 'ParamHandR',
  'ParamArmLBust', 'ParamArmRBust',
  // 呼吸
  'ParamBreath',
  // 身体动作
  'ParamBody', 'ParamBodyLean', 'ParamBodyTilt',
  'ParamBodySway', 'ParamBodyRoll',
  // 毛发/物理
  'ParamHairFront', 'ParamHairBack', 'ParamHairSide',
  'ParamHairFlutter', 'ParamHair',
  'ParamBust', 'ParamBustX', 'ParamBustY',
  'ParamSkirt', 'ParamDress',
  // Haru 特有
  'ParamTere', 'ParamMune', 'ParamEyeSmile',
  'ParamBrowLY', 'ParamBrowRY', 'ParamBrowLAngle', 'ParamBrowRAngle',
  'ParamCheek', 'ParamTear', 'ParamJoy',
  'ParamNose', 'ParamEar',
  // 更多变体
  'PARAM_ANGLE_X', 'PARAM_ANGLE_Y', 'PARAM_ANGLE_Z',
  'PARAM_BODY_ANGLE_X', 'PARAM_BODY_ANGLE_Y', 'PARAM_BODY_ANGLE_Z',
  'PARAM_EYE_BALL_X', 'PARAM_EYE_BALL_Y',
  'PARAM_MOUTH_OPEN_Y', 'PARAM_MOUTH_FORM',
  'PARAM_BREATH',
  'PARAM_ARM_L', 'PARAM_ARM_R',
]

const foundParams = []
const paramCount = coreModel.getParameterCount()
console.log(`总参数数量: ${paramCount}`)

for (const pid of KNOWN_PARAMS) {
  try {
    const idx = coreModel.getParameterIndex(pid)
    if (idx >= 0 && idx < paramCount) {
      const val = coreModel.getParameterValueByIndex(idx)
      const min = coreModel.getParameterMinimumValue(idx)
      const max = coreModel.getParameterMaximumValue(idx)
      const def = coreModel.getParameterDefaultValue(idx)
      foundParams.push({ id: pid, idx, val, min, max, def })
      console.log(`  ✅ [${idx}] ${pid} = ${val?.toFixed(3)} (范围: ${min?.toFixed(1)} ~ ${max?.toFixed(1)})`)
    }
  } catch(e) {}
}

console.log(`\n发现 ${foundParams.length}/${KNOWN_PARAMS.length} 个已知参数`)

// =====================================================
// PART 2: 动作组发现
// =====================================================
console.log('\n===== PART 2: 动作组 & 索引探测 =====')

const GROUPS = ['', 'Idle', 'TapBody', 'TapHead', 'TapArm', 'TapHand', 'Gesture', 'Emotion', 'Talk', 'Action', 'Motion', 'Event', 'Special']
const foundMotions = {}

for (const g of GROUPS) {
  for (let i = 0; i < 15; i++) {
    try {
      // 尝试启动动作但不强制覆盖
      model.motion(g, i, { force: false })
      // 如果能走到这里说明动作存在
      if (!foundMotions[g]) foundMotions[g] = []
      foundMotions[g].push(i)
    } catch(e) {
      // 动作不存在，继续
    }
  }
}

console.log('可用动作组:')
for (const [g, indices] of Object.entries(foundMotions)) {
  console.log(`  🎬 ${g || '(空=Idle)'}: 索引 [${indices.join(', ')}]`)
}

// =====================================================
// PART 3: 表达式发现
// =====================================================
console.log('\n===== PART 3: 表情发现 =====')

// 尝试多种表达式管理器路径
const exprPaths = [
  'internalModel.expressionManager',
  'internalModel.coreModel',
  '_expressionManager',
]

let expressions = []
for (const path of exprPaths) {
  try {
    const mgr = path.split('.').reduce((o, k) => o?.[k], model)
    if (mgr) {
      console.log(`  表达式管理器路径: model.${path}`)
      // 尝试获取表情定义
      if (mgr._expressions) {
        expressions = [...mgr._expressions]
      } else if (mgr.getExpressionIds) {
        try { expressions = mgr.getExpressionIds() } catch(e) {}
      } else if (mgr.getExpressions) {
        try { expressions = mgr.getExpressions() } catch(e) {}
      }
      if (expressions.length) break
    }
  } catch(e) {}
}

if (expressions.length) {
  console.log(`  可用表情 (${expressions.length}):`, expressions)
} else {
  console.log('  ⚠️ 未找到表情管理器，尝试直接设置表达式名称...')
  const TEST_EXPR = ['F01', 'F02', 'F03', 'F04', 'F05', 'F06', 'F07', 'F08']
  for (const e of TEST_EXPR) {
    try {
      model.expression(e)
      console.log(`  ✅ 表情 "${e}" 设置成功`)
    } catch(err) {
      console.log(`  ❌ 表情 "${e}" 不可用`)
    }
  }
}

// =====================================================
// PART 4: 肢体动作测试
// =====================================================
console.log('\n===== PART 4: 肢体参数实时控制测试 =====')

// 测试身体相关参数
const bodyParams = foundParams.filter(p =>
  ['body', 'arm', 'hand', 'angle', 'breath'].some(k => p.id.toLowerCase().includes(k))
)

if (bodyParams.length) {
  console.log('身体相关参数:', bodyParams.map(p => p.id).join(', '))
  console.log('\n🧪 测试每个身体参数 ±0.5 变化 (2秒后自动恢复):')

  for (const p of bodyParams) {
    const origVal = p.val
    // 正向测试
    coreModel.setParameterValueByIndex(p.idx, Math.min(p.max, origVal + 0.5))
    await new Promise(r => setTimeout(r, 300))
    // 负向测试
    coreModel.setParameterValueByIndex(p.idx, Math.max(p.min, origVal - 0.5))
    await new Promise(r => setTimeout(r, 300))
    // 恢复
    coreModel.setParameterValueByIndex(p.idx, origVal)
    console.log(`  ✅ ${p.id}: 测试完成 (原始=${origVal.toFixed(3)})`)
  }
} else {
  console.log('⚠️ 未发现身体相关参数')
}

// =====================================================
// PART 5: 部件发现
// =====================================================
console.log('\n===== PART 5: 部件 (Parts) 发现 =====')

const partCount = coreModel.getPartCount?.() ?? 0
console.log(`部件数量: ${partCount}`)

// 尝试用 getPartIndex 探测常见部件
const KNOWN_PARTS = [
  'PartArmL', 'PartArmR', 'PartHandL', 'PartHandR',
  'PartHairFront', 'PartHairBack', 'PartBody', 'PartDress',
  'PartSkirt', 'PartAcc', 'PartRibbon', 'PartItem',
]

for (const pid of KNOWN_PARTS) {
  try {
    const idx = coreModel.getPartIndex?.(pid)
    if (idx !== undefined && idx >= 0) {
      const opacity = coreModel.getPartOpacityByIndex?.(idx) ?? '?'
      console.log(`  ✅ [${idx}] ${pid} = ${opacity}`)
    }
  } catch(e) {}
}

// =====================================================
// 汇总
// =====================================================
console.log('\n===== 📊 诊断汇总 =====')
console.log(`参数总数: ${paramCount} | 已识别: ${foundParams.length} | 未知: ${paramCount - foundParams.length}`)
console.log(`可用动作组: ${Object.keys(foundMotions).length} →`, Object.entries(foundMotions).map(([g, is]) => `${g || 'Idle'}[${is.length}个]`).join(', '))
console.log(`身体参数: ${bodyParams.length} 个 →`, bodyParams.map(p => p.id).join(', ') || '无')

// 导出全局快捷函数
window.$l2d = {
  model,
  coreModel,
  foundParams,
  foundMotions,
  bodyParams,
  // 快捷方法
  set: (id, val) => coreModel.setParameterValueById(id, val),
  get: (id) => coreModel.getParameterValueById(id),
  list: () => foundParams,
  motion: (g, i) => model.motion(g, i, { force: true }),
  listMotions: () => foundMotions,
}

console.log('\n💡 快捷命令已就绪:')
console.log('  $l2d.list()        — 查看所有参数')
console.log('  $l2d.set("参数名", 值)  — 设置参数')
console.log('  $l2d.get("参数名")  — 读取参数')
console.log('  $l2d.motion("组", 索引) — 播放动作')
console.log('  $l2d.listMotions()  — 查看动作组')

})()
