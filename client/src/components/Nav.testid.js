import cleanFilename from "../util/cleanFilename";

const TEST_ID = {
  linkToHome: `${cleanFilename(__filename)}-linkToHome`,
  linkToUsers: `${cleanFilename(__filename)}-linkToUser`,
};

export default TEST_ID;
