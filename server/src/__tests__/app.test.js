import supertest from "supertest";
import app from "../app.js";

const request = supertest(app);

describe("GET /", () => {
  it("Returns a Server is running message as default", (done) => {
    request
      .get("/")
      .then((response) => {
        expect(response.status).toBe(200);
        expect(response.text).toBe("Server is running");

        done();
      })
      .catch((err) => {
        done(err);
      });
  });
});
