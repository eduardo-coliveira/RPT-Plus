import { defineConfig } from 'vite'

export default defineConfig({
  base: '/rtp-plus/',
  server: {
    proxy: {
      '^/(?:login|logout|run_code|diagnose|exercises(?:_python)?|exercise|hint_tree|correct_feedback|notequiv_feedback|log_action)(?:/|\\?|$)': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
