import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.junyi.words',
  appName: 'junyi-word',
  webDir: 'dist',
  server: {
    androidScheme: 'http',  // 使用本地HTTP服务器而非file://, 解决跨域问题
  },
};

export default config;
