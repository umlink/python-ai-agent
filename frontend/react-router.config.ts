import type { Config } from "@react-router/dev/config"

export default {
  // SPA 模式：纯客户端渲染，构建产物为静态文件（build/client）
  ssr: false,
} satisfies Config
