import { logInfo, logWarning, logError } from "../logging.js";

describe("logging", () => {
  it("logInfo should log to the console.log", () => {
    /**
     * Here we tell jest to look at the console.log function so we can track the calls.
     * We also provide a mockImplementation, so that during the test we don't actually write to the console.
     */
    const consoleLogMock = jest.spyOn(console, "log").mockImplementation();

    // first check that it hasn't been called yet
    expect(consoleLogMock).toHaveBeenCalledTimes(0);

    // do your action
    logInfo("Some message");

    // check that it has been called purely by your action
    expect(consoleLogMock).toHaveBeenCalledTimes(1);

    // If we ever mock something with a mockImplementation we ALWAYS need to restore it afterwards, or it will be mocked for other tests
    consoleLogMock.mockRestore();
  });

  it("logWarning should log to the console.warn", () => {
    const consoleWarnMock = jest.spyOn(console, "warn").mockImplementation();

    expect(consoleWarnMock).toHaveBeenCalledTimes(0);

    logWarning("Some message");

    expect(consoleWarnMock).toHaveBeenCalledTimes(1);

    consoleWarnMock.mockRestore();
  });

  it("logError should log simple messages to the console.error", () => {
    const consoleErrorMock = jest.spyOn(console, "error").mockImplementation();

    expect(consoleErrorMock).toHaveBeenCalledTimes(0);

    logError("Some message");

    expect(consoleErrorMock).toHaveBeenCalledTimes(1);

    consoleErrorMock.mockRestore();
  });

  it("logError should log Error objects with stack to the console.error", () => {
    const consoleErrorMock = jest.spyOn(console, "error").mockImplementation();

    expect(consoleErrorMock).toHaveBeenCalledTimes(0);
    // Errors should also log the stack
    const errMessage = "My error";
    const err = new Error(errMessage);
    logError(err);

    expect(consoleErrorMock).toHaveBeenCalledTimes(1);
    expect(consoleErrorMock).toHaveBeenLastCalledWith(errMessage, err.stack);

    consoleErrorMock.mockRestore();
  });
});
