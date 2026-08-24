/**
 * 全局 HTTP client 初始化。
 *
 * 由 main.tsx 顶部 `import '@/api/client'` 触发执行：
 * 注册响应拦截器：响应状态码非 2xx 时统一弹出 antd message.error
 *
 * 业务代码无需感知此文件，直接从 @/client/sdk.gen 导入生成的 SDK 函数即可。
 */

import { message } from 'antd'
import { client } from '@/client/client.gen'
import { formatApiError } from '@/utils/errors'

client.setConfig({
  baseUrl: '',
  // 全局开启抛错：非 2xx 直接抛异常，业务代码可以 try/catch
  // 或交给 react-query 的 isError，不必到处解构 { data, error }
  throwOnError: true,
})

client.interceptors.response.use(async (response) => {
  if (!response.ok) {
    message.error(await formatApiError(response))
  }
  return response
})