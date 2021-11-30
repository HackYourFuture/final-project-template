/**
 * In our models we will have validation checkers that should return an array of error messages.
 * This function creates a nice message for the user of our API saying what is wrong.
 */

// errorList should be an array of strings
const validationErrorMessage = (errorList) => {
  return `BAD REQUEST: ${errorList.join(", ")}`;
};

export default validationErrorMessage;
