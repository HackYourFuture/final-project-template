/// <reference types="cypress" />
const axios = require("axios");

// ***********************************************************
// This example plugins/index.js can be used to load plugins
//
// You can change the location of this file or turn off loading
// the plugins file with the 'pluginsFile' configuration option.
//
// You can read more here:
// https://on.cypress.io/plugins-guide
// ***********************************************************

// This function is called when a project is opened or re-opened (e.g. due to
// the project's config changing)

/**
 * @type {Cypress.PluginConfig}
 */
const baseUrl = "http://localhost:5000";

// eslint-disable-next-line no-unused-vars
module.exports = (on, config) => {
  // `on` is used to hook into various events Cypress emits
  // `config` is the resolved Cypress config

  on("task", {
    "db:seed": async () => {
      const { data } = await axios.post(`${baseUrl}/api/test/seed`);

      return data;
    },
    "db:grabData": (url) => {
      // We use the axios library here as this part runs in node. It was added as a dev dependency
      return axios.get(`${baseUrl}/api${url}`).then((response) => {
        // This function should return the raw data
        return response.data;
      });
    },
  });
};
