import User, { validateUser } from "../models/User";

export const addUserToMockDB = async (newUser) => {
  const validationResult = validateUser(newUser);

  if (validationResult.length > 0) {
    throw new Error(
      `Invalid user attempting to be added to the Database. User attempted to be added: ${JSON.stringify(
        newUser
      )}. Received errors: ${validationResult.join(", ")}.`
    );
  }

  const user = new User(newUser);
  await user.save();
};

export const findUserInMockDB = async (userId) => {
  if (typeof userId !== "string") {
    throw new Error(
      `Invalid userId given! Should be a string, but received: ${userId}`
    );
  }

  const user = await User.findById(userId);

  return user;
};
