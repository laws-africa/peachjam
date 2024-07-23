const { VueLoaderPlugin } = require('vue-loader');
const { sentryWebpackPlugin } = require('@sentry/webpack-plugin');

const peachJamConfig = {
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
      authToken: process.env.SENTRY_AUTH_TOKEN,
      org: 'lawsafrica',
      project: 'lii',
      telemetry: false
    })
  ]
};

module.exports = [peachJamConfig];
