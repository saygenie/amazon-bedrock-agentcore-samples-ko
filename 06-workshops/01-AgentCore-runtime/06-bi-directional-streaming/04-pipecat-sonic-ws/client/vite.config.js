import { defineConfig } from "vite";

export default defineConfig({
  optimizeDeps: {
    include: ["protobufjs/minimal"],
  },
  server: {
    proxy: {
      // 클라이언트가 CORS 문제 없이 WebSocket URL을 가져올 수 있도록
      // /start를 Pipecat 서버로 전달합니다.
      "/start": {
        target: "http://localhost:8081",
        changeOrigin: true,
      },
    },
  },
});
