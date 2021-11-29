import React from "react";
import { BrowserRouter as Router } from "react-router-dom";

/**
 * This component wraps our App with the providers we do not want to have in our tests
 */
const AppWrapper = ({ children }) => {
  return <Router>{children}</Router>;
};

AppWrapper.propTypes = {
  children: React.Node,
};

export default AppWrapper;
