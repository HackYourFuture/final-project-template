/**
 * This is our eslint configuration file for the server.
 * Note: If you make a change here, think about if it should be applied in the server config file as well.
 *
 * ESlint is a way to enforce certain code rules to keep the code base consistent.
 * Have a look at our project repo README or https://eslint.org/ for more information
 */

module.exports = {
  env: {
    node: true,
    browser: true,
    es2021: true,
    jest: true,
  },
  extends: ["eslint:recommended", "plugin:react/recommended"],
  parserOptions: {
    ecmaFeatures: {
      jsx: true,
    },
    ecmaVersion: 12,
    sourceType: "module",
  },
  overrides: [
    {
      files: ["*.jsx", "*.js"],
    },
  ],
  plugins: ["react"],
  rules: {
    quotes: ["error", "double"],
    "no-console": "error",
  },
  settings: {
    react: {
      version: "detect",
    },
  },
};
