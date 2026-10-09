import { defineConfig } from 'vite';

// public/ 下的场景与纸片图一变，整页刷新（位置由 main.ts 在开发模式下存取）
export default defineConfig({
  base: process.env.BASE_PATH ?? (process.env.GITHUB_ACTIONS ? '/nexus/' : '/'),
  // 绑定 IPv4 回环：localhost 可能只解析到 ::1，导致 127.0.0.1 打不开
  server: {
    host: '127.0.0.1',
  },
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
