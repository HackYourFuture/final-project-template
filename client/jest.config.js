module.exports = {
  testEnvironment: "jsdom",
  setupFilesAfterEnv: ["./setupTests.js"],
  moduleNameMapper: {
    "\\.(css|less)$": "<rootDir>/__mocks__/styleMock.js",
    "\\.(jpg|jpeg|png|svg)$": "<rootDir>/__mocks__/fileMock.js",
  },
};
