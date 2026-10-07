import { defineConfig } from 'vite';

// public/ 下的场景与纸片图一变，整页刷新（位置由 main.ts 在开发模式下存取）
export default defineConfig({
  plugins: [
    {
      name: 'nexus-reload-assets',
      configureServer(server) {
        server.watcher.add(['public/scenes', 'public/sprites']);
        server.watcher.on('change', (f) => {
          if (/[\/]public[\/](scenes|sprites)[\/]/.test(f)) server.ws.send({ type: 'full-reload' });
        });
      },
    },
  ],
});
