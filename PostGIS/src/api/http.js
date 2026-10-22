// axios 统一封装：实例 + 请求/响应拦截器

import axios from 'axios'

const http = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

// 请求拦截器：过滤空参数，避免拼接无用 query
http.interceptors.request.use((config) => {
  if (config.params) {
    const filtered = {}
    for (const [k, v] of Object.entries(config.params)) {
      if (v !== undefined && v !== null && v !== '') filtered[k] = v
    }
    config.params = filtered
  }
  return config
})

// 响应拦截器：直接返回响应体；错误统一转为 Error(message)
http.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const message =
      error.response?.data?.error?.message ||
      error.message ||
      '请求失败'
    return Promise.reject(new Error(message))
  },
)

export default http
