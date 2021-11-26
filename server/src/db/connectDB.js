import mongoose from "mongoose";

const connectDB = () => mongoose.connect(process.env.MONGODB_URL);

export default connectDB;
