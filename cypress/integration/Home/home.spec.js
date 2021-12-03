/// <reference types="cypress" />

import TEST_ID_HOME from "../../../client/src/pages/Home/Home.testid";

describe("Home page", () => {
  it("Go to the Home page", () => {
    cy.visit("/");
  });

  it("The Home page is showing", () => {
    cy.getByTestId(TEST_ID_HOME.container).should("be.visible");
  });
});
