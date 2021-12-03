/// <reference types="cypress" />

import TEST_ID_CREATE_USER from "../../../client/src/pages/User/CreateUser.testid";
import TEST_ID_USER_LIST from "../../../client/src/pages/User/UserList.testid";
import TEST_ID_NAV from "../../../client/src/components/Nav.testid";

describe("createuser", () => {
  beforeEach(() => {
    cy.task("db:seed");
  });

  it("Should be able to create a user and it shows in the list", () => {
    cy.visit("/user");
    const testUser = "SOME_UNIQUE_NAME";
    const testUserEmail = "SOME@UNIQUE.COM";

    cy.requestFromDatabase("/user").then((data) => {
      const initialUserCount = data.result.length;

      cy.getByTestId(TEST_ID_USER_LIST.userList)
        .children()
        .should("have.length", initialUserCount);

      cy.log(`Initially ${initialUserCount} users detected`);

      cy.clickByTestId(TEST_ID_USER_LIST.createUserButton);

      // Fill in fields
      cy.getByTestId(TEST_ID_CREATE_USER.nameInput).type(testUser);
      cy.getByTestId(TEST_ID_CREATE_USER.emailInput).type(testUserEmail);

      cy.clickByTestId(TEST_ID_CREATE_USER.submitButton);

      // Check user is added to the list
      cy.clickByTestId(TEST_ID_NAV.linkToUsers);

      cy.getByTestId(TEST_ID_USER_LIST.userList)
        .children()
        .should("have.length", initialUserCount + 1);
    });
  });
});
