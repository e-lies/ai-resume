import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Le front parle à l'API par le même domaine : aucun CORS à gérer.
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
})
