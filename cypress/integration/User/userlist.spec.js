/// <reference types="cypress" />

import TEST_ID_USER_LIST from "../../../client/src/pages/User/UserList.testid";

describe("userlist", () => {
  beforeEach(() => {
    cy.task("db:seed");
  });

  it("Should show the users in the database", () => {
    cy.requestFromDatabase("/user").then((data) => {
      const users = data.result;
      cy.visit("/user");
      cy.getByTestId(TEST_ID_USER_LIST.container).should("be.visible");

      users.forEach((user) => {
        cy.getByElementId(user._id).should("be.visible");
      });
    });
  });
});
