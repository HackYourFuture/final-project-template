import cleanFilename from "../../util/cleanFilename";

const TEST_ID = {
  container: `${cleanFilename(__filename)}-container`,
  nameInput: `${cleanFilename(__filename)}-nameInput`,
  emailInput: `${cleanFilename(__filename)}-emailInput`,
  submitButton: `${cleanFilename(__filename)}-submitButton`,
  loadingContainer: `${cleanFilename(__filename)}-loadingContainer`,
  errorContainer: `${cleanFilename(__filename)}-errorContainer`,
};

export default TEST_ID;
