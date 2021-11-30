import validationErrorMessage from "../validationErrorMessage.js";

describe("validationErrorMessage", () => {
  it("Adds every error message in the given list to the message", () => {
    const result = validationErrorMessage(["foo", "bar"]);
    expect(result).toContain("foo");
    expect(result).toContain("bar");
  });

  /**
   * We want to make sure that if the function is being used in the wrong way that the function throws an error.
   * If we don't and it will silently allow it, we could be creating silent bugs!
   */
  it("Throws an error if the parameter is unexpected", () => {
    expect(() => validationErrorMessage(null)).toThrow();
    expect(() =>
      validationErrorMessage({ errorList: ["foo", "bar"] })
    ).toThrow();
  });
});
