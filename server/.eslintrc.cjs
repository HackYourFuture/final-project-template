/**
 * This is our eslint configuration file for the server.
 * Note: If you make a change here, think about if it should be applied in the client config file as well.
 *
 * ESlint is a way to enforce certain code rules to keep the code base consistent.
 * Have a look at our project repo README or https://eslint.org/ for more information
 */

module.exports = {
  env: {
    browser: true,
    es2021: true,
  },
  plugins: ["prettier"],
  // We use the airbnb style guide as a base. More information about that here: https://github.com/airbnb/javascript
  extends: ["airbnb-base"],
  parserOptions: {
    ecmaVersion: 13,
    sourceType: "module",
  },
  rules: {
    // block any code that is not formatted according to prettier formatting rules
    "prettier/prettier": "error",
    // turned off the rule to make everything a default export
    "import/prefer-default-export": "off",
  },
};
