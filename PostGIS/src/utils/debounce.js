// 防抖工具：视口 moveend 后延迟请求，避免高频触发
export function debounce(fn, wait = 300) {
  let timer = null
  return (...args) => {
    clearTimeout(timer)
    timer = setTimeout(() => fn(...args), wait)
  }
}
