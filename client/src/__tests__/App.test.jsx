import React from "react";
import { render } from "@testing-library/react";
import App from "../App";

describe("App", () => {
  it("Should have hello world message", () => {
    const { getByText } = render(<App />);

    expect(getByText("Hello world React!")).toBeInTheDocument();
  });
});
