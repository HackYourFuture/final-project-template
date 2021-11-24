import supertest from "supertest";
import app from "../app.js";

const request = supertest(app);

describe("GET /api/status", () => {
  it("Returns a Server is running message as default", (done) => {
    request
      .get("/api/status")
      .then((response) => {
        expect(response.status).toBe(200);
        expect(response.text).toContain("Server is running on port:");

        done();
      })
      .catch((err) => {
        done(err);
      });
  });
});
