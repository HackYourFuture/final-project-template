import express from "express";
import cors from "cors";

import userRouter from "./routes/user.js";

// Create an express server
const app = express();

// Tell express to use the json middleware
app.use(express.json());
// Allow everyone to access our API. In a real application, we would need to restrict this!
app.use(cors());

// TODO: A simple route to test with, will be removed once everything is set up
app.get("/api/status", (req, res) =>
  res.send({
    running: true,
    message: `Server is running on port: ${process.env.PORT}`,
  })
);

/****** Attach routes ******/
/**
 * We use /api/ at the start of every route!
 * As we also host our client code on heroku we want to separate the API endpoints.
 */
app.use("/api/user", userRouter);

export default app;
