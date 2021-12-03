import createTestIdFilePath from "../../util/createTestIdFilePath";

const TEST_ID = {
  container: `${createTestIdFilePath("pages", "User", "CreateUser")}-container`,
  nameInput: `${createTestIdFilePath("pages", "User", "CreateUser")}-nameInput`,
  emailInput: `${createTestIdFilePath(
    "pages",
    "User",
    "CreateUser"
  )}-emailInput`,
  submitButton: `${createTestIdFilePath(
    "pages",
    "User",
    "CreateUser"
  )}-submitButton`,
  loadingContainer: `${createTestIdFilePath(
    "pages",
    "User",
    "CreateUser"
  )}-loadingContainer`,
  errorContainer: `${createTestIdFilePath(
    "pages",
    "User",
    "CreateUser"
  )}-errorContainer`,
};

export default TEST_ID;
