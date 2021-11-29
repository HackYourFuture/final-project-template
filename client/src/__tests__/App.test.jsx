import React from "react";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import App from "../App";
import HomeTestIds from "../pages/Home/Home.testid";
import UserListTestIds from "../pages/User/UserList.testid";
import CreateUserTestIds from "../pages/User/CreateUser.testid";

beforeEach(() => {
  fetch.resetMocks();
});

describe("Routing", () => {
  it("Path '/' should go to Home page ", () => {
    const { getByTestId } = render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    );

    expect(getByTestId(HomeTestIds.container)).toBeInTheDocument();
  });

  it("Path '/user' should go to User list ", async () => {
    fetch.mockResponseOnce(JSON.stringify({ success: true, result: [] }));

    render(
      <MemoryRouter initialEntries={["/user"]}>
        <App />
      </MemoryRouter>
    );

    expect(
      await screen.findByTestId(UserListTestIds.container)
    ).toBeInTheDocument();
  });

  it("Path '/user/create' should go to User create page ", async () => {
    const { getByTestId } = render(
      <MemoryRouter initialEntries={["/user/create"]}>
        <App />
      </MemoryRouter>
    );

    expect(getByTestId(CreateUserTestIds.container)).toBeInTheDocument();
  });
});
