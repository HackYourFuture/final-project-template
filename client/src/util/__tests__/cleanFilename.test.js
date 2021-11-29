import cleanFilename from "../cleanFilename";

describe("cleanFilename", () => {
  it("Cuts off everything before src", () => {
    expect(
      cleanFilename(
        "/My/file/system/final-project-template/client/src/pages/User/UserList.testid.js-container"
      )
    ).toBe("/src/pages/User/UserList.testid.js-container");
  });
});
