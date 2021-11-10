// Load our .env variables
import dotenv from "dotenv";

import app from "./app.js";
import { logInfo, logError } from "./util/logging.js";

dotenv.config();

// The environment should set the port
const { PORT } = process.env;

if (PORT == null) {
  // If this fails, make sure you have created a `.env` file in the right place with the PORT set
  logError(new Error("Cannot find a PORT number, did you create a .env file?"));
}

app.listen(PORT, () => {
  logInfo(`Server started on port ${PORT}`);
});
