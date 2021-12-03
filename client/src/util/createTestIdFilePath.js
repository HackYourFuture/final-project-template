/**
 * This file is used to create the TEST_ID file paths
 */
const createTestIdFilePath = (...args) => {
  return args.join("/");
};

export default createTestIdFilePath;
