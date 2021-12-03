import express from "express";
import mongoose from "mongoose";
import User, { validateUser } from "./models/User.js";

import { logError } from "./util/logging.js";
import validationErrorMessage from "./util/validationErrorMessage.js";

const testRouter = express.Router();

testRouter.post("/seed", async (req, res) => {
  if (!process.env.MONGODB_URL.includes("cypressDatabase")) {
    const msg =
      "The database you are trying to seed is not the cypress database! Did you forget to change your .env variable?";
    logError(msg);

    res.status(400).json({
      sucess: false,
      msg,
    });
  } else {
    await emptyDatabase();

    const data = {
      users: [
        {
          name: "Rob",
          email: "rob@hackyourfuture.net",
        },
      ],
    };

    // Validate users to the database
    data.users.forEach((user) => {
      const errorList = validateUser(user);

      if (errorList.length > 0) {
        const err = new Error(
          `Invalid user in seed data. Errors: ${validationErrorMessage(
            errorList
          )}. User attempting to be inserted: ${JSON.stringify(user)}`
        );

        logError(err);
        throw err;
      }
    });

    // Add users to the database
    await User.create(data.users);

    // Fetch to add to the return
    const finalUsers = await User.find();

    res.status(201).json({
      success: true,
      data: {
        users: finalUsers,
      },
    });
  }
});

const emptyDatabase = async () => {
  const collections = mongoose.connection.collections;

  for (const key in collections) {
    const collection = collections[key];
    await collection.deleteMany({});
  }
};

export default testRouter;
