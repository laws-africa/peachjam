const { VueLoaderPlugin } = require('vue-loader');
const { sentryWebpackPlugin } = require('@sentry/webpack-plugin');

module.exports = (env, argv) => {
  return [{
    mode: 'development',
    resolve: {
      alias: {
        vue: '@vue/runtime-dom'
      },
      modules: [
        './node_modules'
      ],
      extensions: ['.tsx', '.ts', '.js']
    },
    entry: {
      app: './peachjam/js/app.ts',
      'pdf.worker': 'pdfjs-dist/build/pdf.worker.entry'
    },
    module: {
      rules: [
        {
          test: /\.vue$/,
          use: [
            {
              loader: 'vue-loader',
              options: {
                compilerOptions: {
                  isCustomElement: tag => tag.startsWith('la-')
                }
              }
            }
          ]
        },
        {
          test: /\.tsx?$/,
          use: 'ts-loader',
          exclude: /node_modules/
        },
        {
          test: /\.css$/,
          use: ['vue-style-loader', 'css-loader']
        },
        {
          test: /\.scss$/,
          use: ['vue-style-loader', 'css-loader', 'sass-loader']
        }
      ]
    },
    output: {
      filename: '[name]-prod.js',
      path: __dirname + '/peachjam/static/js'
    },
    devtool: 'source-map',
    plugins: [
      new VueLoaderPlugin(),
      sentryWebpackPlugin({
        disable: argv.mode !== 'production',
        authToken: process.env.SENTRY_AUTH_TOKEN,
        org: 'lawsafrica',
        project: 'lii',
        telemetry: false,
        applicationKey: 'peachjam-frontend',
        // Runtime Django settings provide the application release to both the
        // browser and Python SDKs. Keep Debug ID source-map uploads here, but
        // do not create a competing frontend-only release at build time.
        release: {
          create: false,
          finalize: false,
          inject: false
        }
      })
    ]
  }];
}
