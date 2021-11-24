// Load our .env variables
import dotenv from "dotenv";

import app from "./app.js";
import { logInfo, logError } from "./util/logging.js";

dotenv.config();

// The environment should set the port
const port = process.env.PORT;

if (port == null) {
  // If this fails, make sure you have created a `.env` file in the right place with the PORT set
  logError(new Error("Cannot find a PORT number, did you create a .env file?"));
}

/****** Host our client code for Heroku *****/
/**
 * We only want to host our client code when in production as we then want to use the production build.
 * When not in production, don't host the files, but the development version of the app can connect to the backend itself.
 */
if (process.env.NODE_ENV === "production") {
  app.use(
    express.static(new URL("../../client/dist", import.meta.url).pathname)
  );
  // Redirect * requests to give the client data
  app.get("*", (req, res) =>
    res.sendFile(
      new URL("../../client/dist/index.html", import.meta.url).pathname
    )
  );
}

// Start listening
app.listen(port, () => {
  logInfo(`Server started on port ${port}`);
});
