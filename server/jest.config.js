export default {
  transform: {
    "^.+\\.jsx?$": "babel-jest",
  },
  modulePathIgnorePatterns: ["__testUtils__"],
  transformIgnorePatterns: [],
};
