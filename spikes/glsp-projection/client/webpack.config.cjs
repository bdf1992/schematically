// CommonJS on purpose: the package's own "type": "module" would otherwise
// make webpack read this as ESM, and webpack's config loader wants CJS here.
const path = require('path');

module.exports = {
    mode: 'development',
    devtool: 'source-map',
    entry: path.resolve(__dirname, 'app.mjs'),
    output: {
        filename: 'bundle.js',
        path: path.resolve(__dirname, 'dist')
    },
    resolve: {
        extensions: ['.mjs', '.js']
    },
    module: {
        rules: [{ test: /\.css$/, use: ['style-loader', 'css-loader'] }]
    }
};
