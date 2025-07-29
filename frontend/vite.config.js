import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueJsx from '@vitejs/plugin-vue-jsx'
import path from 'path'
import frappeui from 'frappe-ui/vite'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    frappeui({
      frappeProxy: true,
      lucideIcons: true,
      jinjaBootData: true,
      buildConfig: {
        indexHtmlPath: '../erplite/www/erplite.html',
        emptyOutDir: true,
        sourcemap: true,
      },
    }),
    vue(),
    vueJsx(),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  build: {
    outDir: '../erplite/public/frontend',
    emptyOutDir: true,
    sourcemap: false, // Disable sourcemaps to reduce memory usage
    minify: 'esbuild', // Use esbuild for faster, less memory-intensive minification
    rollupOptions: {
      output: {
        manualChunks: {
          // Split vendor chunks to reduce memory usage during build
          vue: ['vue'],
          icons: ['@iconify/vue'],
          primevue: ['primevue/config', 'primevue/button', 'primevue/card']
        }
      }
    },
    chunkSizeWarningLimit: 1000, // Increase chunk size limit
  },
  base: '/assets/erplite/frontend/',
})
