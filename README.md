# Class XX final project

## Stack / deployment libraries

The base stack of the app is a MERN stack (Mongoose, Express, React, Node). Next to that we make use of the following extras:

- `dotenv` - To load the .env variables into the process environment. See [docs](https://www.npmjs.com/package/dotenv)
- `webpack` - To bundle our React app and create a static app to host. See [docs](https://webpack.js.org/)

## Developing / dev libraries

To start developing, both the client and the server have the following command to set up the developer environment:

`npm run dev`

On the server this will run `nodemon` so that any changes automatically cause a restart of the server.

### Testing

For testing we use `jest` on both the client and server side. For the client we use the `react-testing-library` (see documentation [here](https://testing-library.com/docs/react-testing-library/intro/)). For the server side we use `supertest` (see documentation [here](https://github.com/visionmedia/supertest)).

### Automation configuration

We have some checks that runs automatically and ensures that we as a team are consistent in styling and code. To accomplish that we use a combination of prettier, eslint and husky to run tests. These will also be run on every PR that goes to the `develop` and `main` branches in our project. Have a look below for explanations on each of these tools and what they do.

#### Prettier

We use prettier to ensure that our code is formatted consistently. The `client` and `server` both have their own configuration files to allow for differences between the two if absolutely necessary.

To run a check for code formatting use `npm run prettier`. To autofix issues run `npm run prettier:fix`.

#### ESlint

We use ESlint to ensure that our code is styled consistently. The `client` and `server` both have their own configuration files to allow for differences between the two if absolutely necessary. We extend from the base airbnb styles mentioned [here](https://github.com/airbnb/javascript) and write a comment for any changes.

To run a check for code style use `npm run lint`. To try to autofix issues run `npm run lint:fix`.

If there is a lint error that you feel is unjustified you can discuss with the team if it should be added to the ignore rules (see eslint documentation for that [here](https://eslint.org/docs/user-guide/configuring/rules)). If it is a one time exception to be made you can use disable comments, like so:

```js
/* eslint-disable no-console */

console.log("bar");

/* eslint-enable no-console */
```

Make sure you add a comment to explain why the exception is needed.

#### Husky

We use Husky to automatically run our lint/prettier checks as well as our tests before committing files. This will ensure that any code that is pushed is according to our code styles and is fully tested. You can run these tests yourself aswell by running:

`npm run pre-commit`

Remember that there are commands to run autofixes for lint/prettier, have a look at the `package.json` to see what is available.

If you are confident nothing is broken you can write `git commit --no-verify` to allow github to do the checks!
