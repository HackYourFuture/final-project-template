import validateAllowedFields from "../validateAllowedFields.js";

describe("validateAllowedFields", () => {
  it("Returns an empty string if all fields are allowed", () => {
    expect(validateAllowedFields({ foo: "bar" }, ["foo"])).toBe("");
    expect(
      validateAllowedFields({ foo: "bar" }, ["foo", "some_other_field"])
    ).toBe("");
  });

  it("Returns an error string containing the right field name if the field is not allowed", () => {
    expect(validateAllowedFields({ foo: "bar" }, [])).toContain("foo");

    const resultForMultipleFields = validateAllowedFields(
      { foo: "bar", other: "something" },
      ["foo"]
    );
    expect(resultForMultipleFields).toContain("other");
    expect(resultForMultipleFields).not.toContain("foo");
  });

  /**
   * We want to make sure that if the function is being used in the wrong way that the function throws an error.
   * If we don't and it will silently allow it, we could be creating silent bugs!
   */
  it("Throws an error if the parameters have the wrong types", () => {
    expect(() => validateAllowedFields()).toThrow();
    expect(() => validateAllowedFields(["foo"], { foo: "bar" })).toThrow();
    expect(() => validateAllowedFields({ foo: "bar" })).toThrow();
  });
});
