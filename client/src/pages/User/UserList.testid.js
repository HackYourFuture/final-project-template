import cleanFilename from "../../util/cleanFilename";

const TEST_ID = {
  container: `${cleanFilename(__filename)}-container`,
  loadingContainer: `${cleanFilename(__filename)}-loadingContainer`,
  errorContainer: `${cleanFilename(__filename)}-errorContainer`,
  userList: `${cleanFilename(__filename)}-userList`,
};

export default TEST_ID;
