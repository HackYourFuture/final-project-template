/**
 * This is our eslint configuration file for the server.
 * Note: If you make a change here, think about if it should be applied in the client config file as well.
 *
 * ESlint is a way to enforce certain code rules to keep the code base consistent.
 * Have a look at our project repo README or https://eslint.org/ for more information
 */

module.exports = {
  env: {
    node: true,
    es2021: true,
    jest: true,
  },
  extends: ["eslint:recommended"],
  plugins: ["prettier"],
  parserOptions: {
    ecmaVersion: 13,
    sourceType: "module",
  },
  rules: {
    // prettier does double quotes so make that the default
    quotes: ["error", "double"],
    // block any code that is not formatted according to prettier formatting rules
    "prettier/prettier": "error",
    // turned off the rule to make everything a default export
    "import/prefer-default-export": "off",
    // turned off the rule that you should not have file extensions. For modules in node this is actually required
    "import/extensions": "off",
    "no-console": "warn",
  },
};
