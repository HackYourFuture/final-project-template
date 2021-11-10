require("dotenv").config();
const express = require("express");

const { logInfo, logError } = require("./util/logging");

// Create an express server
const app = express();

// Tell express to use the json middleware
app.use(express.json());

app.get("/", (req, res) => res.send("Hello World!"));

// The environment should set the port
const { PORT } = process.env;

if (PORT == null) {
  // If this fails, make sure you have created a `.env` file in the right place with the PORT set
  logError(new Error("Cannot find a PORT number, did you create a .env file?"));
}

app.listen(PORT, () => {
  logInfo(`Server started on port ${PORT}`);
});
