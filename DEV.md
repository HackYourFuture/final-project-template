# Configuration

We have set up a CI/CD pipeline that will automatically run tests and deploy the code to heroku when new pull requests are made. There are a lot of moving parts, so let's go through it step by step.

## 1. Development

To start developing, make sure you have created the `.env` files and did the setup step as described in the main [README](./README.md). This will run both the client and the server. If you want to run them in separate terminals you can run `npm run dev` in each folder to just start that one.

### 1.1 Client

The client will be built using `webpack`. The configuration for that is in the `webpack.config.js` file. When running in production the command `npm run build` will be run which will create a `dist` folder with the compiled version of the code. When running in dev mode the `webpack-dev-server` will build it in memory. This will also automatically rebuild on file changes!

Our client will always run on `https://localhost:8080`. So if it does not automatically open your browser you can go to that URL. It will connect to the URL put in the `.env` file, defaulting to `https://localhost:5000`.

You will also notice that to connect to the server our `useFetch` hook adds `/api` to the url. This is because on `heroku` our backend not only has its own routes but also hosts the client code. This way it allows us to differentiate between what needs to return the client code and what is an actual request to our backend.

### 1.2 Server

The server will be run from the `index.js` file. This is separate from the `app.js` for testing purposes. In dev mode it will be ran using `nodemon`, in production using `node`. The `.env` determines the port and the URL to the mongodb database. If you change the port here, then don't forget to also change it on the client side.

You probably want to set up your own personal mongodb database for your own usage so that you don't interfere with other developers and use that url most of the time.

There are two lines of `MONGODB_URL` in the `.env` file. This is because one should be used for `cypress` and the other for regular development. We've added an extra failsafe in the seeding code to only do that when connected to the `cypressDatabase` so that we don't accidentally erase someone's data.

## 2. Testing

On both the client and the server side we use the `jest` framework for testing. As mentioned in the [README](./README.md) each side has their own extra libraries to mock out certain parts to create isolated tests. The jest configuration of each side is in the `jest.config.js` file.

In both the client and the server you can run the command `npm run test:watch` to have the tests automatically run whenever you change something. This will speed up your ability to fix tests.

If you want to check the code coverage of the tests, run the command `npm run test:coverage`! This can help you identify if you have missed some parts. 100% coverage is generally not possible, nor does 100% means that it is tested perfectly, but it is a tool you can use.

### 2.1 Client

On the client side, we want to unit test our components by isolating them. You can use `jest-fetch-mock` to mock any fetches made to the api. We use the `__testUtils__` folder to combine these responses in one place so that all of our tests can use them. Our api is subject to change, so it will also help make these changes less impactful.

Any utility functions should have their own test, there is a `__test__` folder in the `util` folder for exactly that purpose.

Remember to clean up the mocks before you start each test that is going to use those mocks by writing the code below at the top of your file:

```
beforeEach(() => {
  fetch.resetMocks();
});
```

For the client code we want to use the `data-testid` attributes as ways to target the elements in our tests. This will serve as points for our QA engineers to interact with the elements as well in the `cypress` tests. This is also the reason why every component has a `.testid.js` file to store the test ids in. We can then access those in `cypress` without having to load all of the client code.

### 2.2 Server

On the server side, we want to test our end points, not our specific controllers/routes. For that we can use `supertest` to send requests and then use the mocked database provided by `mongodb-memory-server` to make assertions on the database. To create a certain state of the database the `__testUtils__` folder provides functions to add things to the database.

Remember that you always want to start every test with a clean database so that other test will not interfere. This is why we have the following code in every test file:

```
beforeAll(async () => {
  await connectToMockDB();
});

afterEach(async () => {
  await clearMockDatabase();
});

afterAll(async () => {
  await closeMockDatabase();
});
```

### 2.3 Cypress

To do our integration test we use `cypress`. This will run a browser and allow you to assert using the DOM. `Cypress` is a little more difficult to run as it requires all communication with the client and server to go via the browser. It should be totally separate as it needs to test an application as close to reality as possible.

When you want to add or run a `cypress` test, you have to first make sure that you are connecting to the `cypressDatabase` with your server by adjusting the `.env` file. You can open the test GUI by running `npm run cypress` from the main directory. From there you can run the tests individually with a view of the browser.

In our CI/CD the tests will be run headless, the command to try that locally is `npm run test:cypress`.

The tests should be in the `integration` folder. In that folder we try to mimic a bit how the pages are structured in the app, but some deviation is expected.

To access elements in the page, make sure to use the `data-testid` or `data-elementid` values. There are custom commands to get those in the `support` folder. Feel free to add to those!

If your test interacts with the database, remember to add the following code to your test:

```
  beforeEach(() => {
    cy.task("db:seed");
  });
```

This will run the `/api/test/seed` function which will seed our database with our standard data. If you need more data initially then feel free to add to this function. You will also need to access this data so your test will not fail if the data is slightly changed. To do that you can use the `requestFromDatabase` custom command. This will send a request to the database and give you back the information. Using a `.then` you can then design a test that takes the data into account. The code that does the interaction with the database is in the `plugins` folder.

## 3. Pushing

Once you have created your code and tests, it is time to push it. The `husky` library will run all of the tests and some checks on your code to ensure it is up to the standards. In the `.husky/pre-commit` file you can see what commands are run. If this fails, your commit will not have been created and you will need to fix the problems before trying again. Make sure that you add the files you changed to the commit before running again!

By doing this, you will get an earlier notification if something will not pass our CI/CD tests which will speed it all up. If you want to skip this check you can run `git commit --no-verify`.

## 4. Deploying

Whenever a PR is made in our github, the pipelines start working. In the `.github/workflows` folder you will find some yml files that define actions github will take whenever a new commit is pushed to a PR. The `client-code-style-check`, `server-code-style-check` will run the linter on the code. The `client-tests` and `server-tests` will run the jest tests in their respective folders and the `cypress-tests` will run the cypress tests headlessly. All of these have to pass for code to be allowed to be merged in! In the `Actions` tab in github you can see the results of the run if there is something broken.

If the cypress tests fail and you are unsure why, the cypress job in the `Actions` tab will have an artifact that has all of the videos of the run. You can download these to see the browser as it was running through your test.

Every PR will also have its own deployed version on heroku. In the PR there will be a link to this version so you can see how it runs in the deployed/production state. This is what the QA engineers can use to test the application.
