import express from "express";
import cors from "cors";

// Create an express server
const app = express();

// Tell express to use the json middleware
app.use(express.json());
// Allow everyone to access our API. In a real application, we would need to restrict this!
app.use(cors());

app.get("/api/status", (req, res) =>
  res.send({
    running: true,
    message: `Server is running on port: ${process.env.PORT}`,
  })
);

export default app;
