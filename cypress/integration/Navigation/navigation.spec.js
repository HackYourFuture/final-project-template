/// <reference types="cypress" />

import TEST_ID_HOME from "../../../client/src/pages/Home/Home.testid";
import TEST_ID_NAV from "../../../client/src/components/Nav.testid";
import TEST_ID_USER_LIST from "../../../client/src/pages/User/UserList.testid";
import TEST_ID_CREATE_USER from "../../../client/src/pages/User/CreateUser.testid";

describe("Navigation", () => {
  it("From home page", () => {
    cy.visit("/");
    cy.getByTestId(TEST_ID_HOME.container).should("be.visible");

    checkNavigation();
  });

  it("From user list page", () => {
    cy.visit("/user");
    cy.getByTestId(TEST_ID_USER_LIST.container).should("be.visible");

    checkNavigation();
  });

  it("From create user page", () => {
    cy.visit("/user/create");
    cy.getByTestId(TEST_ID_CREATE_USER.container).should("be.visible");

    checkNavigation();
  });
});

const checkNavigation = () => {
  // go to users page
  cy.clickByTestId(TEST_ID_NAV.linkToUsers);
  cy.getByTestId(TEST_ID_USER_LIST.container).should("be.visible");

  // go to create user page
  cy.clickByTestId(TEST_ID_USER_LIST.createUserButton);
  cy.getByTestId(TEST_ID_CREATE_USER.container).should("be.visible");

  // go to home
  cy.clickByTestId(TEST_ID_NAV.linkToHome);
  cy.getByTestId(TEST_ID_HOME.container).should("be.visible");
};
