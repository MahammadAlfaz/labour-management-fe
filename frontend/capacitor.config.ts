import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.alfaz.labourmanagement',
  appName: 'Labour Management',
  webDir: 'dist',
  server: {
    // Load the live Vercel deployment instead of a locally bundled build, so
    // the WebView stays on the same origin as the /api proxy -- the exact
    // cookie setup that already works for mobile Safari/Chrome today.
    url: 'https://labour-management-fe-pi.vercel.app',
    androidScheme: 'https',
  },
  android: {
    // Strips the WebView "wv" UA marker that makes Google Sign-In refuse to
    // run inside an embedded WebView ("disallowed_useragent" error).
    overrideUserAgent:
      'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
  },
};

export default config;
