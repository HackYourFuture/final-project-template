/**
 * Adapted from https://kimlehtinen.com/how-to-setup-jest-for-node-js-mongoose-typescript-projects/
 */

import mongoose from "mongoose";
import { MongoMemoryServer } from "mongodb-memory-server";

let mongoMemServer;

/**
 * Connecting to the Database
 */
export const connectToMockDB = async () => {
  if (mongoMemServer != null) {
    // Prevent us from overwriting the database when tests are running!
    throw Error(
      `Error in testing, mongoMemServer should not be set when calling connectToMockDB. mongoMemServer should be null or undefined, but received: ${mongoMemServer.toString()}`
    );
  }

  mongoMemServer = await MongoMemoryServer.create();
  const uri = mongoMemServer.getUri();

  await mongoose.connect(uri);
};

/**
 * Closing the Database connection
 */
export const closeMockDatabase = async () => {
  // Get rid of the database
  await mongoose.connection.dropDatabase();
  // close the mongoose connection
  await mongoose.connection.close();
  // stop the memory server
  await mongoMemServer.stop();

  // clean up the variable
  mongoMemServer = null;
};

/**
 * Clear the database, used to clean between tests
 */
export const clearMockDatabase = async () => {
  const collections = mongoose.connection.collections;

  for (const key in collections) {
    const collection = collections[key];
    await collection.deleteMany({});
  }
};
