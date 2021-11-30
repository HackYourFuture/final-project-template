import supertest from "supertest";

import {
  connectToMockDB,
  closeMockDatabase,
  clearMockDatabase,
} from "../__testUtils__/dbMock.js";
import app from "../app.js";
import { findUserInMockDB } from "../__testUtils__/userMocks.js";

const request = supertest(app);

beforeAll(async () => {
  await connectToMockDB();
});

afterEach(async () => {
  await clearMockDatabase();
});

afterAll(async () => {
  await closeMockDatabase();
});

const testUserBase = { name: "John", email: "john@doe.com" };

describe("POST /api/user/create", () => {
  it("Should return a bad request if no user object is given", (done) => {
    request
      .post("/api/user/create")
      .then((response) => {
        expect(response.status).toBe(400);

        const { body } = response;
        expect(body.success).toBe(false);
        // Check that there is an error message
        expect(body.msg.length).not.toBe(0);

        done();
      })
      .catch((err) => {
        done(err);
      });
  });

  it("Should return a bad request if the user object does not have a name", (done) => {
    const testUser = { email: testUserBase.email };

    request
      .post("/api/user/create")
      .send({ user: testUser })
      .then((response) => {
        expect(response.status).toBe(400);

        const { body } = response;
        expect(body.success).toBe(false);
        // Check that there is an error message
        expect(body.msg.length).not.toBe(0);

        done();
      })
      .catch((err) => {
        done(err);
      });
  });

  it("Should return a bad request if the user object does not have an email", (done) => {
    const testUser = { name: testUserBase.name };

    request
      .post("/api/user/create")
      .send({ user: testUser })
      .then((response) => {
        expect(response.status).toBe(400);

        const { body } = response;
        expect(body.success).toBe(false);
        // Check that there is an error message
        expect(body.msg.length).not.toBe(0);

        done();
      })
      .catch((err) => {
        done(err);
      });
  });

  it("Should return a bad request if the user object has extra fields", (done) => {
    const testUser = { ...testUserBase, foo: "bar" };

    request
      .post("/api/user/create")
      .send({ user: testUser })
      .then((response) => {
        expect(response.status).toBe(400);

        const { body } = response;
        expect(body.success).toBe(false);
        // Check that there is an error message
        expect(body.msg.length).not.toBe(0);

        done();
      })
      .catch((err) => {
        done(err);
      });
  });

  it("Should return a success state if a correct user is given", async () => {
    const testUser = { ...testUserBase };

    return request
      .post("/api/user/create")
      .send({ user: testUser })
      .then((response) => {
        expect(response.status).toBe(201);

        const { body } = response;
        expect(body.success).toBe(true);
        expect(body.user.name).toEqual(testUser.name);
        expect(body.user.email).toEqual(testUser.email);

        // Check that it was added to the DB
        return findUserInMockDB(body.user._id);
      })
      .then((userInDb) => {
        expect(userInDb.name).toEqual(testUser.name);
        expect(userInDb.email).toEqual(testUser.email);
      });
  });
});
