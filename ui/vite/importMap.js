/**
 * Defines the document's import map and omits the specified entries from the bundle.
 *
 * @param {string} mode - The current Vite mode (e.g., 'development' or 'production').
 * @param {Object.<string, string>} entries - A map of module specifiers to URLs.
 * @returns {import('vite').Plugin}
 */
export default function importMap(mode, entries) {
  return {
    name: 'importMap',
    config() {
      const config = {
        build: {
          rollupOptions: {
            external: Object.keys(entries),
          },
        },
      };

      if (mode === 'development') {
        config.resolve = {
          alias: entries,
        };
      }

      return config;
    },
    transformIndexHtml(html) {
      const imports = Object.entries(entries)
        .map(([key, value]) => `"${key}":"${value}"`)
        .join(',');

      const importMapScript = `<script type="importmap">{"imports":{${imports}}}</script>`;
      return html.replace(
        /^(\s*?)<title>.*?<\/title>/m,
        `$&$1${importMapScript}`
      );
    },
  };
}
