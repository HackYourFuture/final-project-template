import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import App from "../App";
import TEST_ID_HOME from "../pages/Home/Home.testid";
import TEST_ID_USER_LIST from "../pages/User/UserList.testid";
import TEST_ID_CREATE_USER from "../pages/User/CreateUser.testid";
import { getUsersSuccessMock } from "../__testUtils__/fetchUserMocks";

beforeEach(() => {
  fetch.resetMocks();
});

describe("Routing", () => {
  it("Path '/' should go to Home page ", () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    );

    expect(screen.getByTestId(TEST_ID_HOME.container)).toBeInTheDocument();
  });

  it("Path '/user' should go to User list ", async () => {
    fetch.mockResponseOnce(getUsersSuccessMock());

    render(
      <MemoryRouter initialEntries={["/user"]}>
        <App />
      </MemoryRouter>
    );

    await waitFor(() =>
      expect(
        screen.getByTestId(TEST_ID_USER_LIST.container)
      ).toBeInTheDocument()
    );
  });

  it("Path '/user/create' should go to User create page ", () => {
    render(
      <MemoryRouter initialEntries={["/user/create"]}>
        <App />
      </MemoryRouter>
    );

    expect(
      screen.getByTestId(TEST_ID_CREATE_USER.container)
    ).toBeInTheDocument();
  });
});
