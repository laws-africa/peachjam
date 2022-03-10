const { VueLoaderPlugin } = require('vue-loader')

const peachJamConfig = {
  mode: 'development',
  resolve: {
    alias: {
      'vue': '@vue/runtime-dom',
    },
    modules: [
      './node_modules',
    ],
    extensions: ['.tsx', '.ts', '.js'],
  },
  entry: {
    app: './peach_jam/js/app.ts',
  },
  module: {
    rules: [
      {
        test: /\.vue$/,
        use: [
          {
            loader: 'vue-loader'
          }
        ]
      },
      {
        test: /\.tsx?$/,
        use: 'ts-loader',
        exclude: /node_modules/,
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
    filename: 'app-prod.js',
    path: __dirname + '/peach_jam/static/js'
  },
  plugins: [
      new VueLoaderPlugin(),
  ]
};

module.exports = [peachJamConfig];
