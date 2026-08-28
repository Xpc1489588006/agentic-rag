import { defineConfig } from '@hey-api/openapi-ts'

export default defineConfig({
  // 用 127.0.0.1 而非 localhost：Node 的 fetch 可能把 localhost 解析到 IPv6 ::1，
  // 而 uvicorn 只监听 IPv4，会导致生成时请求挂起超时（operation was aborted）
  input: 'http://127.0.0.1:8000/openapi.json',
  output: 'src/client',
  plugins: [
    '@hey-api/client-fetch',
    '@hey-api/typescript',
    '@hey-api/sdk',
  ],
})