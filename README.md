# final-project-template

## Notable libraries

In this section we will add the libraries that we use and what they are used for.

### Prettier

We use prettier to ensure that our code is formatted consistently. The `client` and `server` both have their own configuration files to allow for differences between the two if absolutely necessary.

To run a check for code formatting use `npm run prettier`. To autofix issues run `npm run prettier:fix`.

### ESlint

We use ESlint to ensure that our code is styled consistently. The `client` and `server` both have their own configuration files to allow for differences between the two if absolutely necessary. We extend from the base airbnb styles mentioned [here](https://github.com/airbnb/javascript) and write a comment for any changes.

To run a check for code style use `npm run lint`. To try to autofix issues run `npm run lint:fix`.
