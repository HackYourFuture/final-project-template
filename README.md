# final-project-template

## Notable libraries

In this section we will add the libraries that we use and what they are used for.

### Prettier

We use prettier to ensure that our code is formatted consistently. The `client` and `server` both have their own configuration files to allow for differences between the two if absolutely necessary.

To run a check for code formatting use `npm run prettier`. To autofix issues run `npm run prettier:fix`.

### ESlint

We use ESlint to ensure that our code is styled consistently. The `client` and `server` both have their own configuration files to allow for differences between the two if absolutely necessary. We extend from the base airbnb styles mentioned [here](https://github.com/airbnb/javascript) and write a comment for any changes.

To run a check for code style use `npm run lint`. To try to autofix issues run `npm run lint:fix`.

If there is a lint error that you feel is unjustified you can discuss with the team if it should be added to the ignore rules (see eslint documentation for that [here](https://eslint.org/docs/user-guide/configuring/rules)). If it is a one time exception to be made you can use disable comments, like so:

```js
/* eslint-disable no-console */

console.log("bar");

/* eslint-enable no-console */
```

Make sure you add a comment to explain why the exception is needed.

### Husky

We use Husky to automatically run our lint/prettier checks as well as our tests before committing files. This will ensure that any code that is pushed is according to our code styles and is fully tested. You can run these tests yourself aswell by running:

`npm run pre-commit`

Remember that there are commands to run autofixes for lint/prettier, have a look at the `package.json` to see what is available.
