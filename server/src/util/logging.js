/**
 * Combine all the logging options into one file.
 *
 * For now we log to the console, but if in the future we want to add a logging service
 * we only need to adjust this file.
 */

/**
 * logInfo should be used to log anything that can be used for debugging but is not a problem
 */
const logInfo = (message) => {
  // eslint-disable-next-line no-console
  console.log(message);
};

/**
 * logWarning should be used to log anything that signals a problem that is not app breaking
 */
const logWarning = (message) => {
  // eslint-disable-next-line no-console
  console.warn(message);
};

/**
 * logError should be used to log anything that is app breaking
 */
const logError = (message) => {
  if (message instanceof Error) {
    // You can pass an Error to this function and we will post the stack
    // eslint-disable-next-line no-console
    console.error(message, message.stack);
  } else {
    // eslint-disable-next-line no-console
    console.error("ERROR: ", message);
  }
};

module.exports = {
  logInfo,
  logWarning,
  logError,
};
