/**
 * In this file we can create functions to mock results given by the backend
 */

// Mock of a successful getting of users
export const getUsersSuccessMock = (users = []) => {
  return JSON.stringify({ success: true, result: users });
};

// Mock of a successful getting of users
export const getUsersFailedMock = () => {
  return JSON.stringify({ success: false, msg: "Something went wrong" });
};

// Mock of a successful creation of a new user
export const createUserSuccessMock = (user = {}) => {
  return JSON.stringify({ success: true, user });
};

// Mock of a failing creation of a new user
export const createUserFailedMock = () => {
  return JSON.stringify({ success: false, msg: "Something went wrong" });
};
