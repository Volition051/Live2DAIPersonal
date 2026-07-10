// 纯 DOM Toast，绕过 Vant showToast 的暗色模式/渲染 bug
export function showCustomToast(message, icon = 'success') {
  const el = document.createElement('div')
  const iconChar = icon === 'fail' ? '✕' : '✓'
  const iconColor = icon === 'fail' ? '#ee0a24' : '#07c160'
  el.innerHTML = `<div style="display:flex;flex-direction:column;align-items:center;gap:8px;font-family:sans-serif">
    <span style="font-size:36px;font-weight:bold;color:${iconColor};line-height:1">${iconChar}</span>
    <span style="font-size:14px;color:#323233;font-weight:500">${message}</span>
  </div>`
  el.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);z-index:99999;background:#fff;padding:18px 24px;border-radius:12px;box-shadow:0 8px 30px rgba(0,0,0,.18);min-width:90px;text-align:center'
  document.body.appendChild(el)
  setTimeout(() => el.remove(), 2000)
}
