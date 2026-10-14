import { defineConfig } from 'vite'

export default defineConfig({
  base: '/rtp-plus/',
  server: {
    proxy: {
      '^/rtp-plus/(?:login|logout|run_code|diagnose|exercises(?:_python)?|exercise|hint_tree|correct_feedback|notequiv_feedback|log_action)(?:/|\\?|$)': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/rtp-plus/, ''),
      },
    },
  },
})
