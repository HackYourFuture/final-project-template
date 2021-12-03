import createTestIdFilePath from "../../util/createTestIdFilePath";

const TEST_ID = {
  container: `${createTestIdFilePath("pages", "User", "UserList")}-container`,
  loadingContainer: `${createTestIdFilePath(
    "pages",
    "User",
    "UserList"
  )}-loadingContainer`,
  errorContainer: `${createTestIdFilePath(
    "pages",
    "User",
    "UserList"
  )}-errorContainer`,
  userList: `${createTestIdFilePath("pages", "User", "UserList")}-userList`,
  createUserButton: `${createTestIdFilePath(
    "pages",
    "User",
    "UserList"
  )}-createUserButton`,
};

export default TEST_ID;
