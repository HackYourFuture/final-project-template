import express from "express";

// Create an express server
const app = express();

// Tell express to use the json middleware
app.use(express.json());

app.get("/", (req, res) => res.send("Server is running"));

export default app;
