const path = require('path');
const webpack = require('webpack');

const HtmlWebpackPlugin = require('html-webpack-plugin');

const nodeEnv = process.env.NODE_ENV || 'development';
const isProd = nodeEnv === 'production';

module.exports = {
    entry: {
        app: './frontend/js/main.jsx',
    },

    output: {
        path: path.resolve(__dirname, '..'),
        filename: 'js/[name]-[hash].bundle.js',
        publicPath: '/',
    },

    module: {
        rules: [{
            test: /\.css$/,
            use: [
                'style-loader',
                'css-loader'
            ]
        }, {
            test: /\.(js|jsx)$/,
            exclude: /node_modules/,
            use: {
                loader: "babel-loader"
            }
        }, {
            test: /\.(woff|woff2|eot|ttf)$/,
            loader: 'url-loader?limit=100000'
        }, {
            test: /\.(png|svg|jpg|gif|ico)$/,
            use: [{
                loader: 'file-loader',
                options: { name: 'img/[name].[ext]'}
            } ]
        }]
    },

    plugins: [
        new HtmlWebpackPlugin({
            filename: './index.html',
            title: 'Motuz File Transfer',
            minify: true,
            meta: {
            }
        }),
        new webpack.ProvidePlugin({
            $: 'jquery',
            jQuery: 'jquery'
        }),
    ],

    resolve: {
        modules: [
            path.resolve('./frontend/js'),
            path.resolve('./frontend/css'),
            path.resolve('./frontend/img'),
            path.resolve('./node_modules')
        ]
    },

    stats: {
        colors: true
    },
};
